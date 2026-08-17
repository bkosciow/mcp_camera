"""Tests for bearer token authentication and fail-closed startup."""

import pytest
from fastapi.testclient import TestClient

from camera_mcp.config import Settings
from camera_mcp.main import create_app

# Must match the value set in tests/conftest.py.
AUTH_TOKEN = "test-token"
AUTH_HEADERS = {"Authorization": f"Bearer {AUTH_TOKEN}"}


class StubCameraManager:
    """Minimal CameraManager stand-in — auth is checked before any camera logic."""

    def __init__(self) -> None:
        self.cameras: list[object] = []

    @property
    def count(self) -> int:
        return len(self.cameras)

    @property
    def last_error(self) -> str | None:
        return None

    def get(self, index: int = 0) -> None:
        return None

    def detect(self) -> int:
        return 0

    def release(self) -> None:
        pass


class TestFailClosed:
    """create_app must refuse to start without a token."""

    @pytest.mark.parametrize("auth_token", [None, "", "   "])
    def test_create_app_raises_without_token(self, auth_token: str | None):
        settings = Settings(auth_token=auth_token, _env_file=None)
        with pytest.raises(RuntimeError, match="CAMERA_AUTH_TOKEN"):
            create_app(settings=settings)


class TestProtectedEndpoints:
    """Every endpoint except /health requires the bearer token."""

    PROTECTED_PATHS = ["/capture", "/capture/0", "/camera", "/camera/0"]

    @pytest.mark.parametrize("path", PROTECTED_PATHS)
    def test_missing_token_returns_401(self, path: str):
        app = create_app(camera=StubCameraManager())
        with TestClient(app) as client:
            response = client.get(path)
        assert response.status_code == 401

    @pytest.mark.parametrize("path", PROTECTED_PATHS)
    def test_wrong_token_returns_401(self, path: str):
        app = create_app(camera=StubCameraManager())
        with TestClient(app) as client:
            response = client.get(path, headers={"Authorization": "Bearer wrong-token"})
        assert response.status_code == 401

    @pytest.mark.parametrize("path", PROTECTED_PATHS)
    def test_valid_token_reaches_camera_layer(self, path: str):
        """With the right token the request passes auth (never 401).

        The stub manager has no cameras, so /capture* yields 404 and
        /camera (no index) yields 200 — anything but 401 proves auth passed.
        """
        app = create_app(camera=StubCameraManager())
        with TestClient(app) as client:
            response = client.get(path, headers=AUTH_HEADERS)
        assert response.status_code in (200, 404)

    def test_health_open_without_token(self):
        app = create_app(camera=StubCameraManager())
        with TestClient(app) as client:
            response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "degraded"

    def test_401_body_shape(self):
        app = create_app(camera=StubCameraManager())
        with TestClient(app) as client:
            response = client.get("/capture")
        assert response.json() == {"detail": "Invalid or missing token"}
        assert response.headers["WWW-Authenticate"] == "Bearer"
