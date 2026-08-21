"""Integration tests for /capture and /health endpoints."""

import numpy as np
from fastapi.testclient import TestClient

from camera_mcp.camera import CameraError
from camera_mcp.config import Settings
from camera_mcp.main import create_app

# Must match the value set in tests/conftest.py.
AUTH_HEADERS: dict[str, str] = {"Authorization": "Bearer test-token"}


def _make_frame(width: int = 640, height: int = 480) -> np.ndarray:
    """Create a random test frame."""
    return np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)


class MockSingleCamera:
    """Mock SingleCamera for integration tests."""

    def __init__(self, device, connected=True, capture_fail=False):
        self._device = device
        self._connected = connected
        self._capture_fail = capture_fail
        self._capture_count = 0
        self._last_error = None if connected else f"Failed to open camera: {device}"

    @property
    def device(self):
        return self._device

    @property
    def connected(self):
        return self._connected

    @property
    def last_error(self):
        return self._last_error

    def capture(self, max_width: int = 1280) -> bytes:
        self._capture_count += 1
        if self._capture_fail:
            self._connected = False
            self._last_error = "Camera unavailable"
            raise CameraError("Camera unavailable")
        frame = _make_frame()
        if max_width < frame.shape[1]:
            scale = max_width / frame.shape[1]
            new_w = int(frame.shape[1] * scale)
            new_h = int(frame.shape[0] * scale)
            frame = np.resize(frame, (new_h, new_w, 3))
        import cv2

        _, buf = cv2.imencode(".jpg", frame)
        return buf.tobytes()

    def current_resolution(self):
        if not self._connected:
            return (0, 0)
        return (1920, 1080)

    def available_resolutions(self):
        if not self._connected:
            return []
        return [(640, 480), (1280, 720), (1920, 1080)]

    def release(self):
        self._connected = False


class MockCameraManager:
    """Mock CameraManager for integration tests."""

    def __init__(self, camera_configs=None):
        if camera_configs is None:
            camera_configs = [(0, True, False)]
        self._cameras = [
            MockSingleCamera(device, connected, fail)
            for device, connected, fail in camera_configs
        ]

    def detect(self):
        return len(self._cameras)

    @property
    def count(self):
        return len(self._cameras)

    @property
    def connected(self):
        return len(self._cameras) > 0

    @property
    def camera_device(self):
        return self._cameras[0].device if self._cameras else None

    @property
    def last_error(self):
        return self._cameras[0].last_error if self._cameras else None

    def get(self, index: int = 0):
        try:
            return self._cameras[index]
        except IndexError:
            return None

    @property
    def cameras(self):
        return list(self._cameras)

    def capture(self, max_width: int = 1280) -> bytes:
        if not self._cameras:
            raise CameraError("No camera available")
        return self._cameras[0].capture(max_width=max_width)

    def current_resolution(self):
        if not self._cameras:
            return (0, 0)
        return self._cameras[0].current_resolution()

    def available_resolutions(self):
        if not self._cameras:
            return []
        return self._cameras[0].available_resolutions()

    def release(self):
        for cam in self._cameras:
            cam.release()


def make_app(camera_configs=None):
    """Create app with a mocked CameraManager."""
    mock = MockCameraManager(camera_configs=camera_configs)
    app = create_app(camera=mock)
    return app, mock


# ---------------------------------------------------------------------------
# /capture tests (default - first camera)
# ---------------------------------------------------------------------------


class TestCaptureEndpoint:
    """Integration tests for GET /capture."""

    def test_capture_returns_200_with_jpeg(self):
        app, _ = make_app()
        with TestClient(app, headers=AUTH_HEADERS) as client:
            response = client.get("/capture")
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/jpeg"
            assert len(response.content) > 0
            assert response.content[:2] == b"\xff\xd8"

    def test_capture_returns_503_when_camera_unavailable(self):
        app, _ = make_app(camera_configs=[(0, True, True)])
        with TestClient(app, headers=AUTH_HEADERS) as client:
            response = client.get("/capture")
            assert response.status_code == 503
            data = response.json()
            assert "error" in data
            assert "code" in data
            assert data["code"] == "CAMERA_UNAVAILABLE"

    def test_capture_respects_max_width(self):
        app, _ = make_app()
        with TestClient(app, headers=AUTH_HEADERS) as client:
            response = client.get("/capture?max_width=640")
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/jpeg"

    def test_capture_rejects_width_too_large(self):
        app, _ = make_app()
        with TestClient(app, headers=AUTH_HEADERS) as client:
            response = client.get("/capture?max_width=9999")
            assert response.status_code == 422

    def test_capture_rejects_width_too_small(self):
        app, _ = make_app()
        with TestClient(app, headers=AUTH_HEADERS) as client:
            response = client.get("/capture?max_width=99")
            assert response.status_code == 422

    def test_consecutive_captures_return_different_data(self):
        app, _ = make_app()
        with TestClient(app, headers=AUTH_HEADERS) as client:
            r1 = client.get("/capture")
            r2 = client.get("/capture")
            assert r1.status_code == 200
            assert r2.status_code == 200
            assert r1.content != r2.content


# ---------------------------------------------------------------------------
# /capture/{index} tests
# ---------------------------------------------------------------------------


class TestCaptureIndexEndpoint:
    """Integration tests for GET /capture/{index}."""

    def test_capture_index_returns_200_for_existing_camera(self):
        app, _ = make_app(camera_configs=[(0, True, False), (1, True, False)])
        with TestClient(app, headers=AUTH_HEADERS) as client:
            response = client.get("/capture/1")
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/jpeg"
            assert response.content[:2] == b"\xff\xd8"

    def test_capture_index_returns_404_for_missing_camera(self):
        app, _ = make_app()
        with TestClient(app, headers=AUTH_HEADERS) as client:
            response = client.get("/capture/5")
            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["error"]

    def test_capture_index_respects_max_width(self):
        app, _ = make_app(camera_configs=[(0, True, False), (1, True, False)])
        with TestClient(app, headers=AUTH_HEADERS) as client:
            response = client.get("/capture/1?max_width=640")
            assert response.status_code == 200


# ---------------------------------------------------------------------------
# /camera tests
# ---------------------------------------------------------------------------


class TestCameraEndpoint:
    """Integration tests for GET /camera."""

    def test_camera_returns_all_cameras(self):
        app, _ = make_app(camera_configs=[(0, True, False), (1, True, False)])
        with TestClient(app, headers=AUTH_HEADERS) as client:
            response = client.get("/camera")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 2
            assert len(data["cameras"]) == 2
            assert data["cameras"][0]["index"] == 0
            assert data["cameras"][0]["connected"] is True
            assert data["cameras"][1]["index"] == 1
            assert data["cameras"][1]["connected"] is True

    def test_camera_single_camera(self):
        app, _ = make_app()
        with TestClient(app, headers=AUTH_HEADERS) as client:
            response = client.get("/camera")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 1
            assert len(data["cameras"]) == 1
            first_cam = data["cameras"][0]
            assert first_cam["connected"] is True
            assert first_cam["current_resolution"] is not None

    def test_camera_no_cameras(self):
        app, _ = make_app(camera_configs=[])
        with TestClient(app, headers=AUTH_HEADERS) as client:
            response = client.get("/camera")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 0
            assert data["cameras"] == []


class TestCameraIndexEndpoint:
    """Integration tests for GET /camera/{index}."""

    def test_camera_index_returns_info(self):
        app, _ = make_app(camera_configs=[(0, True, False), (1, True, False)])
        with TestClient(app, headers=AUTH_HEADERS) as client:
            response = client.get("/camera/1")
            assert response.status_code == 200
            data = response.json()
            assert data["index"] == 1
            assert data["connected"] is True
            assert data["device"] == 1
            assert data["current_resolution"] is not None

    def test_camera_index_returns_404(self):
        app, _ = make_app()
        with TestClient(app, headers=AUTH_HEADERS) as client:
            response = client.get("/camera/5")
            assert response.status_code == 404
            data = response.json()
            assert "not found" in data["error"]


# ---------------------------------------------------------------------------
# /health tests
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Integration tests for GET /health."""

    def test_health_ok_when_camera_connected(self):
        app, _ = make_app()
        with TestClient(app, headers=AUTH_HEADERS) as client:
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["camera_count"] == 1

    def test_health_degraded_when_no_cameras(self):
        app, _ = make_app(camera_configs=[])
        with TestClient(app, headers=AUTH_HEADERS) as client:
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert data["camera_count"] == 0

    def test_health_includes_uptime(self):
        app, _ = make_app()
        with TestClient(app, headers=AUTH_HEADERS) as client:
            response = client.get("/health")
            data = response.json()
            assert "uptime_seconds" in data
            assert isinstance(data["uptime_seconds"], (int, float))
            assert data["uptime_seconds"] >= 0

    def test_health_includes_last_error_null_when_ok(self):
        app, _ = make_app()
        with TestClient(app, headers=AUTH_HEADERS) as client:
            response = client.get("/health")
            data = response.json()
            assert "last_error" in data
            assert data["last_error"] is None

    def test_health_includes_camera_list(self):
        app, _ = make_app(camera_configs=[(0, True, False), (1, True, False)])
        with TestClient(app, headers=AUTH_HEADERS) as client:
            response = client.get("/health")
            data = response.json()
            assert "cameras" in data
            assert len(data["cameras"]) == 2
            assert data["cameras"][0]["index"] == 0
            assert data["cameras"][0]["connected"] is True
            assert data["cameras"][1]["index"] == 1

    def test_health_includes_camera_device(self):
        app, _ = make_app()
        with TestClient(app, headers=AUTH_HEADERS) as client:
            response = client.get("/health")
            data = response.json()
            assert len(data["cameras"]) == 1
            first_cam = data["cameras"][0]
            assert first_cam["device"] == 0

    def test_health_place_defaults_to_default(self):
        app, _ = make_app()
        with TestClient(app, headers=AUTH_HEADERS) as client:
            response = client.get("/health")
            data = response.json()
            assert data["place"] == "default"
            assert data["places"] == ["default"]

    def test_health_includes_configured_places(self):
        settings = Settings(_env_file=None, auth_token="test-token", places="default,home")
        mock = MockCameraManager(camera_configs=[(0, True, False)])
        custom_app = create_app(camera=mock, settings=settings)
        with TestClient(custom_app, headers=AUTH_HEADERS) as client:
            response = client.get("/health")
            data = response.json()
            assert data["place"] == "home"
            assert data["places"] == ["default", "home"]
