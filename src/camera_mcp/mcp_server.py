"""MCP server — exposes camera capture as tools for Claude Code.

Run with:
    uv run python -m camera_mcp.mcp_server

Or configure in Claude Code settings for automatic stdio transport.
"""

import os

import httpx
from mcp.server.fastmcp import FastMCP, Image

# Configuration from environment
CAMERA_API_URL = os.environ.get("CAMERA_API_URL", "http://localhost:8579")

mcp = FastMCP(
    "Camera MCP",
    instructions="USB camera snapshot service — capture live images and check camera status.",
)


@mcp.tool()
def capture_image(max_width: int = 1280) -> Image:
    """Capture a fresh image from the first USB camera.

    Every call captures a new frame — no stale caches.

    Args:
        max_width: Maximum image width in pixels (160-3840, default 1280).
    """
    url = f"{CAMERA_API_URL}/capture"
    response = httpx.get(url, params={"max_width": max_width}, timeout=10)

    if response.status_code != 200:
        raise RuntimeError(f"Capture failed (HTTP {response.status_code}): {response.text}")

    return Image(data=response.content, format="jpeg")


@mcp.tool()
def camera_status() -> str:
    """Check camera health and connection status.

    Returns camera connectivity, device info, uptime, and any recent errors.
    """
    url = f"{CAMERA_API_URL}/health"
    response = httpx.get(url, timeout=5)

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
    mcp.run()


if __name__ == "__main__":
    main()
