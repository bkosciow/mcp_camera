"""Integration tests for /capture and /health endpoints."""

import numpy as np
from fastapi.testclient import TestClient

from camera_mcp.camera import CameraError
from camera_mcp.main import create_app


def _make_frame(width: int = 640, height: int = 480) -> np.ndarray:
    """Create a random test frame."""
    return np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)


class MockCameraManager:
    """Mock CameraManager for integration tests."""

    def __init__(
        self,
        detect_result: bool = True,
        capture_fail: bool = False,
        disconnect_on_capture: bool = False,
    ):
        self._detect_result = detect_result
        self._capture_fail = capture_fail
        self._disconnect_on_capture = disconnect_on_capture
        self._capture_count = 0
        self.connected = detect_result
        self._camera_device = 0 if detect_result else None
        self._last_error = None if detect_result else "No camera found"

    def detect(self) -> bool:
        """Simulate detection — sets connected state."""
        self.connected = self._detect_result
        self._camera_device = 0 if self._detect_result else None
        self._last_error = None if self._detect_result else "No camera found"
        return self._detect_result

    def capture(self, max_width: int = 1280) -> bytes:
        """Simulate capture — returns fresh JPEG bytes or raises."""
        self._capture_count += 1
        if self._capture_fail:
            self.connected = False
            self._last_error = "Camera unavailable"
            raise CameraError("Camera unavailable")
        if self._disconnect_on_capture and self._capture_count > 1:
            self.connected = False
            self._last_error = "Camera disconnected"
            raise CameraError("Camera disconnected")
        frame = _make_frame()
        if max_width < frame.shape[1]:
            scale = max_width / frame.shape[1]
            new_w = int(frame.shape[1] * scale)
            new_h = int(frame.shape[0] * scale)
            frame = np.resize(frame, (new_h, new_w, 3))
        import cv2

        _, buf = cv2.imencode(".jpg", frame)
        return buf.tobytes()

    @property
    def camera_device(self):
        return self._camera_device

    @property
    def last_error(self):
        return self._last_error

    def release(self):
        pass


def make_app(detect_result: bool = True, capture_fail: bool = False):
    """Create app with a mocked CameraManager."""
    mock = MockCameraManager(
        detect_result=detect_result,
        capture_fail=capture_fail,
    )
    app = create_app(camera=mock)
    return app, mock


# ---------------------------------------------------------------------------
# /capture tests
# ---------------------------------------------------------------------------


class TestCaptureEndpoint:
    """Integration tests for GET /capture."""

    def test_capture_returns_200_with_jpeg(self):
        """AC: GET /capture returns 200 with image/jpeg when camera available."""
        app, _ = make_app(detect_result=True)
        with TestClient(app) as client:
            response = client.get("/capture")
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/jpeg"
            assert len(response.content) > 0
            assert response.content[:2] == b"\xff\xd8"

    def test_capture_returns_503_when_camera_unavailable(self):
        """AC: GET /capture returns 503 with JSON error when camera unavailable."""
        app, _ = make_app(capture_fail=True)
        with TestClient(app) as client:
            response = client.get("/capture")
            assert response.status_code == 503
            data = response.json()
            assert "error" in data
            assert "code" in data
            assert data["code"] == "CAMERA_UNAVAILABLE"

    def test_capture_respects_max_width(self):
        """AC: GET /capture?max_width=640 respects width parameter."""
        app, _ = make_app(detect_result=True)
        with TestClient(app) as client:
            response = client.get("/capture?max_width=640")
            assert response.status_code == 200
            assert response.headers["content-type"] == "image/jpeg"

    def test_capture_rejects_width_too_large(self):
        """AC: GET /capture?max_width=9999 rejects out-of-range width (422)."""
        app, _ = make_app(detect_result=True)
        with TestClient(app) as client:
            response = client.get("/capture?max_width=9999")
            assert response.status_code == 422

    def test_capture_rejects_width_too_small(self):
        """AC: GET /capture?max_width=99 rejects below-minimum width (422)."""
        app, _ = make_app(detect_result=True)
        with TestClient(app) as client:
            response = client.get("/capture?max_width=99")
            assert response.status_code == 422

    def test_consecutive_captures_return_different_data(self):
        """AC: Two consecutive GET /capture calls return different image data."""
        app, _ = make_app(detect_result=True)
        with TestClient(app) as client:
            r1 = client.get("/capture")
            r2 = client.get("/capture")
            assert r1.status_code == 200
            assert r2.status_code == 200
            assert r1.content != r2.content


# ---------------------------------------------------------------------------
# /health tests
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Integration tests for GET /health."""

    def test_health_ok_when_camera_connected(self):
        """AC: GET /health returns 200 with status: ok and camera.connected: true."""
        app, _ = make_app(detect_result=True)
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert data["camera"]["connected"] is True

    def test_health_degraded_when_camera_disconnected(self):
        """AC: GET /health returns status: degraded when camera disconnected."""
        app, _ = make_app(detect_result=False)
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert data["camera"]["connected"] is False

    def test_health_includes_uptime(self):
        """AC: Health response includes uptime_seconds >= 0."""
        app, _ = make_app(detect_result=True)
        with TestClient(app) as client:
            response = client.get("/health")
            data = response.json()
            assert "uptime_seconds" in data
            assert isinstance(data["uptime_seconds"], (int, float))
            assert data["uptime_seconds"] >= 0

    def test_health_includes_last_error_null_when_ok(self):
        """AC: Health response includes last_error field — null when no error."""
        app, _ = make_app(detect_result=True)
        with TestClient(app) as client:
            response = client.get("/health")
            data = response.json()
            assert "last_error" in data
            assert data["last_error"] is None

    def test_health_includes_last_error_string_when_degraded(self):
        """AC: Health response includes last_error field — string when error."""
        app, _ = make_app(detect_result=False)
        with TestClient(app) as client:
            response = client.get("/health")
            data = response.json()
            assert "last_error" in data
            assert isinstance(data["last_error"], str)

    def test_health_includes_camera_device(self):
        """AC: Health response includes camera device info."""
        app, _ = make_app(detect_result=True)
        with TestClient(app) as client:
            response = client.get("/health")
            data = response.json()
            assert "device" in data["camera"]
