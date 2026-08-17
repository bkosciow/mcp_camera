"""Tests for the MCP server — verify tool registration and HTTP client behavior."""

from unittest.mock import MagicMock, patch

import pytest


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
