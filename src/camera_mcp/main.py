"""FastAPI application — Camera MCP API."""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Query
from fastapi.responses import JSONResponse, Response

from camera_mcp.camera import CameraError, CameraManager, SingleCamera
from camera_mcp.config import Settings
from camera_mcp.security import make_token_dependency


def create_app(camera: CameraManager | None = None, settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        camera: CameraManager instance (defaults to real singleton).
        settings: Application settings (defaults to get_settings()).

    Raises:
        RuntimeError: If ``settings.auth_token`` is unset or empty — the API
            refuses to start without authentication (fail-closed).
    """
    if settings is None:
        from camera_mcp.config import configure_logging, get_settings

        settings = get_settings()
        configure_logging(settings.log_level)
    if camera is None:
        camera = CameraManager()

    auth_token = (settings.auth_token or "").strip()
    if not auth_token:
        raise RuntimeError(
            "CAMERA_AUTH_TOKEN is not set — refusing to start without authentication. "
            "Set it in the environment or .env file."
        )
    token_dependency = make_token_dependency(auth_token)

    start_time: float = 0.0

    @asynccontextmanager
    async def lifespan(app_obj: FastAPI) -> AsyncIterator[None]:
        """Lifespan handler — detect cameras on startup, release on shutdown."""
        nonlocal start_time
        start_time = time.time()
        camera.detect()
        yield
        camera.release()

    app = FastAPI(title="Camera MCP API", version="0.1.0", lifespan=lifespan)

    def _capture_response(cam: SingleCamera | None, max_width: int) -> Response:
        """Capture from a camera and return the appropriate Response."""
        if cam is None:
            return JSONResponse(
                status_code=404,
                content={"error": "Camera not found"},
            )
        try:
            jpeg_bytes = cam.capture(max_width=max_width)
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

    @app.get("/capture", dependencies=[Depends(token_dependency)])
    async def capture(max_width: int = Query(default=1280, ge=160, le=3840)) -> Response:
        """Capture a fresh image from the first camera.

        Returns a JPEG image resized to the specified max_width.
        Returns 503 if the camera is unavailable.
        """
        return _capture_response(camera.get(0), max_width)

    @app.get("/capture/{cam_index}", dependencies=[Depends(token_dependency)])
    async def capture_index(
        cam_index: int,
        max_width: int = Query(default=1280, ge=160, le=3840),
    ) -> Response:
        """Capture a fresh image from a specific camera.

        Args:
            cam_index: Camera index (0-based).
            max_width: Maximum image width in pixels.

        Returns a JPEG image resized to the specified max_width.
        Returns 404 if the camera index doesn't exist, 503 if unavailable.
        """
        return _capture_response(camera.get(cam_index), max_width)

    @app.get("/camera", dependencies=[Depends(token_dependency)])
    async def camera_info() -> dict[str, Any]:
        """Get info for all detected cameras.

        Returns a list of connected cameras with their device paths,
        connection state, and resolutions.
        """
        cameras_list: list[dict[str, Any]] = []
        for i, cam in enumerate(camera.cameras):
            w, h = cam.current_resolution() if cam.connected else (0, 0)
            resolutions = cam.available_resolutions() if cam.connected else []
            cameras_list.append({
                "index": i,
                "connected": cam.connected,
                "device": cam.device,
                "current_resolution": {"width": w, "height": h} if cam.connected else None,
                "available_resolutions": [
                    {"width": rw, "height": rh} for rw, rh in resolutions
                ],
            })

        return {
            "count": camera.count,
            "cameras": cameras_list,
        }

    @app.get("/camera/{cam_index}", response_model=None, dependencies=[Depends(token_dependency)])
    async def camera_info_index(cam_index: int) -> dict[str, Any] | Response:
        """Get info for a specific camera.

        Args:
            cam_index: Camera index (0-based).

        Returns 404 if the camera index doesn't exist.
        """
        cam = camera.get(cam_index)
        if cam is None:
            return JSONResponse(
                status_code=404,
                content={"error": f"Camera {cam_index} not found"},
            )

        w, h = cam.current_resolution() if cam.connected else (0, 0)
        resolutions = cam.available_resolutions() if cam.connected else []
        return {
            "index": cam_index,
            "connected": cam.connected,
            "device": cam.device,
            "current_resolution": {"width": w, "height": h} if cam.connected else None,
            "available_resolutions": [
                {"width": rw, "height": rh} for rw, rh in resolutions
            ],
        }

    @app.get("/health")
    async def health() -> dict[str, Any]:
        """Check service and camera health.

        Returns service status including all camera connection states,
        uptime, and any recent errors.
        """
        has_camera = camera.count > 0
        cam_errors: list[dict[str, Any]] = []
        for i, cam in enumerate(camera.cameras):
            if cam.last_error:
                cam_errors.append({"index": i, "error": cam.last_error})

        cameras_list: list[dict[str, Any]] = [
            {
                "index": i,
                "connected": cam.connected,
                "device": cam.device,
            }
            for i, cam in enumerate(camera.cameras)
        ]

        status = "ok" if has_camera else "degraded"
        return {
            "status": status,
            "cameras": cameras_list,
            "camera_count": camera.count,
            "uptime_seconds": round(time.time() - start_time, 1),
            "last_error": camera.last_error,
        }

    return app


# Module-level app for production use (uvicorn -m camera_mcp.main:app)
app = create_app()
