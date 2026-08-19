"""MCP server — exposes camera capture as tools for agents.

Run with streamable-http (default, for Docker/deployed use):
    uv run python -m camera_mcp.mcp_server          # → http://0.0.0.0:8580/mcp

Run with stdio (for local Claude Code subprocess):
    MCP_TRANSPORT=stdio uv run python -m camera_mcp.mcp_server
"""

import hmac
import os
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any, Literal

import httpx
import uvicorn
from mcp.server.fastmcp import FastMCP, Image

# Configuration from environment
CAMERA_API_URL = os.environ.get("CAMERA_API_URL", "http://localhost:8579")
MCP_TRANSPORT: Literal["stdio", "sse", "streamable-http"] = (
    os.environ.get("MCP_TRANSPORT", "streamable-http")  # type: ignore[assignment]
)
MCP_HOST = os.environ.get("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.environ.get("MCP_PORT", "8580"))
CAMERA_AUTH_TOKEN = os.environ.get("CAMERA_AUTH_TOKEN", "")
MCP_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")

mcp = FastMCP(
    "Camera MCP",
    instructions="USB camera snapshot service — capture live images and check camera status.",
    host=MCP_HOST,
    port=MCP_PORT,
)


def _auth_headers() -> dict[str, str]:
    """Authorization headers for camera API calls."""
    return {"Authorization": f"Bearer {CAMERA_AUTH_TOKEN}"}


# --- Inbound auth for network transports ------------------------------------

Scope = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[MutableMapping[str, Any]]]
Send = Callable[[MutableMapping[str, Any]], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


def _bearer_token(header: bytes | None) -> bytes | None:
    """Extract the token from an ``Authorization`` header value.

    Returns the raw token bytes when the header is exactly ``Bearer <token>``
    (scheme case-insensitive), else None.
    """
    if header is None:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != b"bearer":
        return None
    return parts[1]


class BearerAuthMiddleware:
    """Pure-ASGI wrapper requiring ``Authorization: Bearer <token>``.

    Non-http scopes (e.g. lifespan) pass through untouched — they carry no
    headers to check. Unauthorized requests get a 401 with
    ``WWW-Authenticate: Bearer`` and never reach the wrapped app.
    """

    def __init__(self, app: ASGIApp, expected_token: str) -> None:
        self.app = app
        self._expected = expected_token.encode("utf-8")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        auth_header: bytes | None = None
        for name, value in scope["headers"]:
            if name == b"authorization":
                auth_header = value
                break
        token = _bearer_token(auth_header)
        if token is not None and hmac.compare_digest(token, self._expected):
            await self.app(scope, receive, send)
            return
        body = b'{"detail": "Invalid or missing token"}'
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"www-authenticate", b"Bearer"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


@mcp.tool()
def capture_image(camera_index: int = 0, max_width: int = 1280) -> Image:
    """Capture a fresh image from a USB camera.

    Every call captures a new frame — no stale caches.

    Args:
        camera_index: Camera index (0-based). Use 0 for the first camera, 1 for the second, etc.
        max_width: Maximum image width in pixels (160-3840, default 1280).
    """

    url = f"{CAMERA_API_URL}/capture/{camera_index}"

    response = httpx.get(url, params={"max_width": max_width}, timeout=10, headers=_auth_headers())

    if response.status_code != 200:
        raise RuntimeError(f"Capture failed (HTTP {response.status_code}): {response.text}")

    return Image(data=response.content, format="jpeg")


@mcp.tool()
def camera_status() -> str:
    """Check camera health and connection status.

    Returns camera connectivity, device info, uptime, and any recent errors.
    """
    url = f"{CAMERA_API_URL}/health"
    response = httpx.get(url, timeout=5, headers=_auth_headers())

    if response.status_code != 200:
        return f"Camera API unreachable: {response.text}"

    data = response.json()
    cameras = data.get("cameras", [])
    count = data.get("camera_count", 0)
    uptime = data.get("uptime_seconds", 0)
    error = data.get("last_error")

    lines = [f"Cameras: {count} detected"]
    for cam in cameras:
        status = "ONLINE" if cam["connected"] else "OFFLINE"
        device = cam.get("device", "unknown")
        lines.append(f"  [{cam['index']}] {status} — {device}")

    lines.append(f"Uptime: {uptime:.0f}s")
    if error:
        lines.append(f"Last error: {error}")

    return "\n".join(lines)


def main() -> None:
    """Entry point for the MCP server."""
    if not CAMERA_AUTH_TOKEN:
        raise SystemExit(
            "CAMERA_AUTH_TOKEN is not set — the camera API requires a bearer token. "
            "Set it in the environment or .env file."
        )
    if MCP_TRANSPORT == "stdio":
        mcp.run(transport="stdio")
        return
    if not MCP_AUTH_TOKEN:
        raise SystemExit(
            "MCP_AUTH_TOKEN is not set — network MCP transports (streamable-http, sse) "
            "require a bearer token. Set it in the environment or .env file, or use "
            "MCP_TRANSPORT=stdio for local subprocess use."
        )
    if MCP_TRANSPORT == "streamable-http":
        app: ASGIApp = mcp.streamable_http_app()
    else:
        app = mcp.sse_app()
    wrapped: ASGIApp = BearerAuthMiddleware(app, MCP_AUTH_TOKEN)
    config = uvicorn.Config(wrapped, host=MCP_HOST, port=MCP_PORT)
    uvicorn.Server(config).run()


if __name__ == "__main__":
    main()
