"""Tests for the MCP server — verify tool registration and HTTP client behavior."""

from unittest.mock import MagicMock, patch

import httpx
import pytest


@pytest.fixture(autouse=True)
def _restore_mcp_instructions():
    """Reset FastMCP instructions after each test (main() mutates the module instance)."""
    from camera_mcp.mcp_server import mcp

    original = mcp._mcp_server.instructions
    yield
    mcp._mcp_server.instructions = original


class TestMCPServerTools:
    """Verify the MCP server exposes the expected tools."""

    def test_tools_are_registered(self):
        """AC: MCP server registers capture_image and camera_status tools."""
        from camera_mcp.mcp_server import mcp

        tools = mcp._tool_manager.list_tools()
        tool_names = [t.name for t in tools]

        assert "capture_image" in tool_names
        assert "camera_status" in tool_names

    def test_server_has_name(self):
        """AC: MCP server has a meaningful name."""
        from camera_mcp.mcp_server import mcp

        assert mcp.name == "Camera MCP"


class TestCaptureImageTool:
    """Test the capture_image tool's HTTP client behavior."""

    def test_capture_returns_jpeg_image(self):
        """AC: capture_image returns an Image with JPEG data on 200 response."""
        from mcp.server.fastmcp import Image

        from camera_mcp.mcp_server import capture_image

        jpeg_bytes = b"\xff\xd8\xff\xe0test-jpeg-data"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = jpeg_bytes

        with patch("camera_mcp.mcp_server.httpx.get", return_value=mock_response):
            result = capture_image()

        assert isinstance(result, Image)
        assert result._mime_type == "image/jpeg"

    def test_capture_passes_max_width_param(self):
        """AC: capture_image forwards max_width to the API query string."""
        from camera_mcp.mcp_server import capture_image

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"\xff\xd8test"

        with patch("camera_mcp.mcp_server.httpx.get", return_value=mock_response) as mock_get:
            capture_image(max_width=640)

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args
        assert call_kwargs[1]["params"]["max_width"] == 640

    def test_capture_raises_on_non_200(self):
        """AC: capture_image raises RuntimeError on non-200 response."""
        from camera_mcp.mcp_server import capture_image

        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Camera unavailable"

        with patch("camera_mcp.mcp_server.httpx.get", return_value=mock_response):
            with pytest.raises(RuntimeError, match="Capture failed"):
                capture_image()


class TestCameraStatusTool:
    """Test the camera_status tool's HTTP client behavior."""

    def test_status_returns_online_when_connected(self):
        """AC: camera_status returns ONLINE string when camera is connected."""
        from camera_mcp.mcp_server import camera_status

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "cameras": [{"index": 0, "connected": True, "device": "/dev/video0"}],
            "camera_count": 1,
            "uptime_seconds": 100.0,
            "last_error": None,
        }

        with patch("camera_mcp.mcp_server.httpx.get", return_value=mock_response):
            result = camera_status()

        assert "ONLINE" in result
        assert "/dev/video0" in result

    def test_status_returns_offline_when_disconnected(self):
        """AC: camera_status returns OFFLINE string when no cameras detected."""
        from camera_mcp.mcp_server import camera_status

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "degraded",
            "cameras": [],
            "camera_count": 0,
            "uptime_seconds": 50.0,
            "last_error": "No camera found",
        }

        with patch("camera_mcp.mcp_server.httpx.get", return_value=mock_response):
            result = camera_status()

        assert "0 detected" in result
        assert "No camera found" in result

    def test_status_handles_multiple_cameras(self):
        """AC: camera_status lists all cameras with their status."""
        from camera_mcp.mcp_server import camera_status

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "cameras": [
                {"index": 0, "connected": True, "device": "/dev/video0"},
                {"index": 1, "connected": False, "device": "/dev/video1"},
            ],
            "camera_count": 2,
            "uptime_seconds": 200.0,
            "last_error": None,
        }

        with patch("camera_mcp.mcp_server.httpx.get", return_value=mock_response):
            result = camera_status()

        assert "2 detected" in result
        assert "ONLINE" in result
        assert "OFFLINE" in result

    def test_status_handles_api_unreachable(self):
        """AC: camera_status returns error message when API is unreachable."""
        from camera_mcp.mcp_server import camera_status

        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("camera_mcp.mcp_server.httpx.get", return_value=mock_response):
            result = camera_status()

        assert "unreachable" in result.lower() or "error" in result.lower()

    def test_status_includes_location_line_for_default_place(self):
        from camera_mcp.mcp_server import camera_status

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "place": "home",
            "places": ["default", "home"],
            "cameras": [{"index": 0, "connected": True, "device": "/dev/video0"}],
            "camera_count": 1,
            "uptime_seconds": 100.0,
            "last_error": None,
        }

        with patch("camera_mcp.mcp_server.httpx.get", return_value=mock_response):
            result = camera_status()

        assert result.startswith("Location: home (default)")

    def test_status_non_default_location_has_no_suffix(self):
        from camera_mcp.mcp_server import camera_status

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "place": "office",
            "places": ["office"],
            "cameras": [],
            "camera_count": 0,
            "uptime_seconds": 1.0,
            "last_error": None,
        }

        with patch("camera_mcp.mcp_server.httpx.get", return_value=mock_response):
            result = camera_status()

        assert result.startswith("Location: office")
        assert "(default)" not in result.splitlines()[0]

    def test_status_omits_location_when_api_reports_none(self):
        from camera_mcp.mcp_server import camera_status

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "cameras": [],
            "camera_count": 0,
            "uptime_seconds": 1.0,
            "last_error": None,
        }

        with patch("camera_mcp.mcp_server.httpx.get", return_value=mock_response):
            result = camera_status()

        assert not result.startswith("Location:")


class TestBuildInstructions:
    """_build_instructions names the deployment's place for agents."""

    def test_default_place_marks_it_default(self):
        from camera_mcp.mcp_server import _build_instructions

        text = _build_instructions("home", ["default", "home"])
        assert "location \"home\"" in text
        assert "Names: default, home" in text
        assert "DEFAULT camera location" in text
        assert "does not specify a location" in text

    def test_non_default_place_is_exclusive(self):
        from camera_mcp.mcp_server import _build_instructions

        text = _build_instructions("office", ["office"])
        assert "location \"office\"" in text
        assert "explicitly asks for the office camera" in text
        assert "DEFAULT" not in text


class TestResolveLocation:
    """_resolve_location reads place/places from the API /health endpoint."""

    def test_returns_place_and_places(self):
        from camera_mcp.mcp_server import _resolve_location

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"place": "home", "places": ["default", "home"]}

        with patch("camera_mcp.mcp_server.httpx.get", return_value=mock_response):
            assert _resolve_location("http://api") == ("home", ["default", "home"])

    def test_falls_back_to_first_place_name(self):
        from camera_mcp.mcp_server import _resolve_location

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"places": ["office"]}

        with patch("camera_mcp.mcp_server.httpx.get", return_value=mock_response):
            assert _resolve_location("http://api") == ("office", ["office"])

    def test_retries_until_healthy(self):
        from camera_mcp.mcp_server import _resolve_location

        bad = MagicMock()
        bad.status_code = 503
        good = MagicMock()
        good.status_code = 200
        good.json.return_value = {"place": "home", "places": ["default", "home"]}

        with (
            patch("camera_mcp.mcp_server.httpx.get", side_effect=[bad, good]),
            patch("camera_mcp.mcp_server.time.sleep"),
        ):
            assert _resolve_location("http://api") == ("home", ["default", "home"])

    def test_returns_none_after_retries(self):
        from camera_mcp.mcp_server import _resolve_location

        with (
            patch("camera_mcp.mcp_server.httpx.get", side_effect=httpx.HTTPError("boom")),
            patch("camera_mcp.mcp_server.time.sleep"),
        ):
            assert _resolve_location("http://api") is None


class TestMCPAuth:
    """The MCP server authenticates against the camera API with a bearer token."""

    def test_capture_sends_auth_header(self):
        from camera_mcp.mcp_server import capture_image

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"\xff\xd8test"

        with patch("camera_mcp.mcp_server.httpx.get", return_value=mock_response) as mock_get:
            with patch("camera_mcp.mcp_server.CAMERA_AUTH_TOKEN", "s3cret"):
                capture_image()

        assert mock_get.call_args[1]["headers"] == {"Authorization": "Bearer s3cret"}

    def test_status_sends_auth_header(self):
        from camera_mcp.mcp_server import camera_status

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "cameras": [],
            "camera_count": 0,
            "uptime_seconds": 1.0,
            "last_error": None,
        }

        with patch("camera_mcp.mcp_server.httpx.get", return_value=mock_response) as mock_get:
            with patch("camera_mcp.mcp_server.CAMERA_AUTH_TOKEN", "s3cret"):
                camera_status()

        assert mock_get.call_args[1]["headers"] == {"Authorization": "Bearer s3cret"}

    def test_main_exits_without_token(self):
        from camera_mcp import mcp_server

        with patch.object(mcp_server, "CAMERA_AUTH_TOKEN", ""):
            with pytest.raises(SystemExit, match="CAMERA_AUTH_TOKEN"):
                mcp_server.main()


async def _echo_app(scope, receive, send):
    """Trivial ASGI app that echoes a 200 JSON body."""
    body = b'{"ok": true}'
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", b"14"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class TestBearerAuthMiddleware:
    """The inbound ASGI middleware enforces a bearer token on http requests."""

    def _client(self, mw):
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=mw), base_url="http://testserver"
        )

    @pytest.mark.parametrize(
        ("headers", "expected"),
        [
            ({"Authorization": "Bearer right-token"}, 200),
            ({"Authorization": "BEARER right-token"}, 200),  # scheme is case-insensitive
            ({}, 401),
            ({"Authorization": "Bearer wrong-token"}, 401),
            ({"Authorization": "Basic right-token"}, 401),
        ],
    )
    async def test_http_requests_checked(self, headers, expected):
        from camera_mcp.mcp_server import BearerAuthMiddleware

        mw = BearerAuthMiddleware(_echo_app, "right-token")
        async with self._client(mw) as client:
            response = await client.get("/mcp", headers=headers)
        assert response.status_code == expected

    async def test_pass_through_returns_inner_response(self):
        from camera_mcp.mcp_server import BearerAuthMiddleware

        mw = BearerAuthMiddleware(_echo_app, "right-token")
        async with self._client(mw) as client:
            response = await client.get("/mcp", headers={"Authorization": "Bearer right-token"})
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    async def test_unauthorized_response_shape(self):
        from camera_mcp.mcp_server import BearerAuthMiddleware

        mw = BearerAuthMiddleware(_echo_app, "right-token")
        async with self._client(mw) as client:
            response = await client.get("/mcp")
        assert response.json() == {"detail": "Invalid or missing token"}
        assert response.headers["www-authenticate"] == "Bearer"

    async def test_non_http_scope_bypasses_auth(self):
        from camera_mcp.mcp_server import BearerAuthMiddleware

        seen = []

        async def recording_app(scope, receive, send):
            seen.append(scope["type"])

        mw = BearerAuthMiddleware(recording_app, "right-token")

        async def receive():
            return {"type": "lifespan.startup"}

        async def send(message):
            pass

        await mw({"type": "lifespan"}, receive, send)
        assert seen == ["lifespan"]


class _FakeUvicornServer:
    """Records uvicorn.Server construction instead of serving."""

    instances: list["_FakeUvicornServer"] = []

    def __init__(self, config) -> None:
        self.config = config
        _FakeUvicornServer.instances.append(self)

    def run(self) -> None:
        pass


class TestMCPStartupAuth:
    """main() enforces MCP_AUTH_TOKEN for network transports (fail-closed)."""

    def test_streamable_http_without_mcp_token_refuses_to_start(self):
        from camera_mcp import mcp_server

        with (
            patch.object(mcp_server, "MCP_TRANSPORT", "streamable-http"),
            patch.object(mcp_server, "CAMERA_AUTH_TOKEN", "api-token"),
            patch.object(mcp_server, "MCP_AUTH_TOKEN", ""),
            patch.object(mcp_server, "_resolve_location", return_value=None),
        ):
            with pytest.raises(SystemExit, match="MCP_AUTH_TOKEN"):
                mcp_server.main()

    def test_stdio_without_mcp_token_still_runs(self):
        from camera_mcp import mcp_server

        runs = []
        with (
            patch.object(mcp_server, "MCP_TRANSPORT", "stdio"),
            patch.object(mcp_server, "CAMERA_AUTH_TOKEN", "api-token"),
            patch.object(mcp_server, "MCP_AUTH_TOKEN", ""),
            patch.object(mcp_server, "_resolve_location", return_value=None),
            patch.object(mcp_server.mcp, "run", lambda transport: runs.append(transport)),
        ):
            mcp_server.main()
        assert runs == ["stdio"]

    def test_streamable_http_serves_token_wrapped_app(self):
        from camera_mcp import mcp_server
        from camera_mcp.mcp_server import BearerAuthMiddleware

        _FakeUvicornServer.instances = []
        with (
            patch.object(mcp_server, "MCP_TRANSPORT", "streamable-http"),
            patch.object(mcp_server, "CAMERA_AUTH_TOKEN", "api-token"),
            patch.object(mcp_server, "MCP_AUTH_TOKEN", "mcp-token"),
            patch.object(mcp_server, "_resolve_location", return_value=None),
            patch.object(mcp_server.uvicorn, "Server", _FakeUvicornServer),
        ):
            mcp_server.main()

        assert len(_FakeUvicornServer.instances) == 1
        config = _FakeUvicornServer.instances[0].config
        assert isinstance(config.app, BearerAuthMiddleware)


class TestMCPStartupLocation:
    """main() derives MCP instructions from the API's /health place fields."""

    def test_main_sets_instructions_for_default_place(self):
        from camera_mcp import mcp_server

        _FakeUvicornServer.instances = []
        with (
            patch.object(mcp_server, "MCP_TRANSPORT", "streamable-http"),
            patch.object(mcp_server, "CAMERA_AUTH_TOKEN", "api-token"),
            patch.object(mcp_server, "MCP_AUTH_TOKEN", "mcp-token"),
            patch.object(
                mcp_server, "_resolve_location", return_value=("home", ["default", "home"])
            ),
            patch.object(mcp_server.uvicorn, "Server", _FakeUvicornServer),
        ):
            mcp_server.main()

        instructions = mcp_server.mcp._mcp_server.instructions
        assert "home" in instructions
        assert "DEFAULT camera location" in instructions

    def test_main_keeps_generic_instructions_when_unresolved(self):
        from camera_mcp import mcp_server

        _FakeUvicornServer.instances = []
        with (
            patch.object(mcp_server, "MCP_TRANSPORT", "streamable-http"),
            patch.object(mcp_server, "CAMERA_AUTH_TOKEN", "api-token"),
            patch.object(mcp_server, "MCP_AUTH_TOKEN", "mcp-token"),
            patch.object(mcp_server, "_resolve_location", return_value=None),
            patch.object(mcp_server.uvicorn, "Server", _FakeUvicornServer),
        ):
            mcp_server.main()

        assert mcp_server.mcp._mcp_server.instructions == (
            "USB camera snapshot service — capture live images and check camera status."
        )
