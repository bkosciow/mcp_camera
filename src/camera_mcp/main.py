"""FastAPI application — Camera MCP API."""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, Response

from camera_mcp.camera import CameraError, CameraManager


def create_app(camera: CameraManager | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        camera: CameraManager instance (defaults to real singleton).
    """
    if camera is None:
        from camera_mcp.config import configure_logging, get_settings

        settings = get_settings()
        configure_logging(settings.log_level)
        camera = CameraManager()

    start_time: float = 0.0

    @asynccontextmanager
    async def lifespan(app_obj: FastAPI) -> AsyncIterator[None]:
        """Lifespan handler — detect camera on startup, release on shutdown."""
        nonlocal start_time
        start_time = time.time()
        camera.detect()
        yield
        camera.release()

    app = FastAPI(title="Camera MCP API", version="0.1.0", lifespan=lifespan)

    @app.get("/capture")
    async def capture(max_width: int = Query(default=1280, ge=160, le=3840)) -> Response:
        """Capture a fresh image from the USB camera.

        Returns a JPEG image resized to the specified max_width.
        Returns 503 if the camera is unavailable.
        """
        try:
            jpeg_bytes = camera.capture(max_width=max_width)
            return Response(
                content=jpeg_bytes,
                media_type="image/jpeg",
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate",
                    "Pragma": "no-cache",
                },
            )
        except CameraError as exc:
            return JSONResponse(
                status_code=503,
                content={"error": str(exc), "code": "CAMERA_UNAVAILABLE"},
            )

    @app.get("/camera")
    async def camera_info() -> dict[str, Any]:
        """Get camera info and available resolutions.

        Probes the camera to discover which resolutions it supports.
        """
        if not camera.connected:
            return {
                "connected": False,
                "device": camera.camera_device,
                "current_resolution": None,
                "available_resolutions": [],
            }

        w, h = camera.current_resolution()
        resolutions = camera.available_resolutions()
        return {
            "connected": True,
            "device": camera.camera_device,
            "current_resolution": {"width": w, "height": h},
            "available_resolutions": [
                {"width": rw, "height": rh} for rw, rh in resolutions
            ],
        }

    @app.get("/health")
    async def health() -> dict[str, Any]:
        """Check service and camera health.

        Returns service status including camera connection state,
        uptime, and any recent errors.
        """
        status = "ok" if camera.connected else "degraded"
        return {
            "status": status,
            "camera": {
                "connected": camera.connected,
                "device": camera.camera_device,
            },
            "uptime_seconds": round(time.time() - start_time, 1),
            "last_error": camera.last_error,
        }

    return app


# Module-level app for production use (uvicorn -m camera_mcp.main:app)
app = create_app()
