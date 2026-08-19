"""Integration tests: bearer auth in front of the real MCP streamable-http app.

The app is served on a real port via uvicorn (in a thread) rather than through
httpx.ASGITransport, because FastMCP's session manager needs an ASGI lifespan
task group that only a real server starts — this also exercises the production
serving path end-to-end.
"""

import socket
import threading
import time
from collections.abc import Iterator

import httpx
import pytest
import uvicorn

from camera_mcp import mcp_server
from camera_mcp.mcp_server import BearerAuthMiddleware

TOKEN = "integration-mcp-token"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class _LiveServer:
    """Serves the token-wrapped MCP app on a real port in a background thread."""

    def __init__(self) -> None:
        self.port = _free_port()
        app = BearerAuthMiddleware(mcp_server.mcp.streamable_http_app(), TOKEN)
        config = uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="error")
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def __enter__(self) -> "_LiveServer":
        self.thread.start()
        deadline = time.monotonic() + 5
        while not self.server.started and time.monotonic() < deadline:
            time.sleep(0.05)
        if not self.server.started:
            raise RuntimeError("MCP server did not start within 5s")
        return self

    def __exit__(self, *_exc: object) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)


# Module-scoped: FastMCP's session manager runs its lifespan only once per app
# instance, so both tests share a single live server.
@pytest.fixture(scope="module")
def live_server() -> Iterator[_LiveServer]:
    with _LiveServer() as server:
        yield server


def test_mcp_endpoint_rejects_missing_token(live_server: _LiveServer) -> None:
    """AC: a request to /mcp without a bearer token gets 401."""
    response = httpx.post(
        f"http://127.0.0.1:{live_server.port}/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
    )
    assert response.status_code == 401


def test_mcp_endpoint_accepts_valid_token(live_server: _LiveServer) -> None:
    """AC: a request with the correct token reaches the real MCP app (not 401)."""
    response = httpx.post(
        f"http://127.0.0.1:{live_server.port}/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize"},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    # A bare initialize without MCP session headers may yield 4xx from the
    # protocol layer — anything but 401 proves the auth wrapper let it through.
    assert response.status_code != 401
