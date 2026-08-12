"""Unit tests for camera module — mocked cv2, no hardware required."""

from unittest.mock import patch

import numpy as np
import pytest

from camera_mcp.camera import CameraError, CameraManager


def _make_frame(width: int = 640, height: int = 480) -> np.ndarray:
    """Create a random test frame."""
    return np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)


def _device_index(device: int | str) -> int:
    """Extract numeric index from device (handles both int and /dev/videoN)."""
    if isinstance(device, int):
        return device
    try:
        return int(device.split("/")[-1].replace("video", ""))
    except ValueError:
        return -1


# ---------------------------------------------------------------------------
# Fixtures — each returns a context manager for use in tests
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_camera_at_0():
    """Mock cv2.VideoCapture to simulate a camera at index 0."""
    frame = _make_frame()

    class VC:
        def __init__(self, device):
            self.opened = _device_index(device) == 0

        def isOpened(self):  # noqa: N802
            return self.opened

        def read(self):
            if not self.opened:
                return False, None
            return True, frame.copy()

        def grab(self):
            return self.opened

        def release(self):
            self.opened = False

        def get(self, prop_id):
            return 0.0

        def set(self, prop_id, value):
            return True

    with patch("cv2.VideoCapture", VC):
        yield


@pytest.fixture
def mock_camera_at_2():
    """Mock cv2.VideoCapture to simulate a camera at index 2."""
    frame = _make_frame()

    class VC:
        def __init__(self, device):
            self.opened = _device_index(device) == 2

        def isOpened(self):  # noqa: N802
            return self.opened

        def read(self):
            if not self.opened:
                return False, None
            return True, frame.copy()

        def grab(self):
            return self.opened

        def release(self):
            self.opened = False

        def get(self, prop_id):
            return 0.0

        def set(self, prop_id, value):
            return True

    with patch("cv2.VideoCapture", VC):
        yield


@pytest.fixture
def mock_no_camera():
    """Mock cv2.VideoCapture to simulate no camera available."""

    class VC:
        def __init__(self, device):
            self.opened = False

        def isOpened(self):  # noqa: N802
            return False

        def read(self):
            return False, None

        def grab(self):
            return self.opened

        def release(self):
            pass

        def get(self, prop_id):
            return 0.0

        def set(self, prop_id, value):
            return True

    with patch("cv2.VideoCapture", VC):
        yield


# ---------------------------------------------------------------------------
# detect() tests
# ---------------------------------------------------------------------------


class TestDetect:
    """Tests for CameraManager.detect()."""

    def test_detect_finds_camera_at_index_0(self, mock_camera_at_0):
        """AC: detect() scans /dev/video* or tries indices 0-5 to find first working camera."""
        manager = CameraManager()
        result = manager.detect()
        assert result is True
        assert manager.connected is True

    def test_detect_returns_false_when_no_camera(self, mock_no_camera):
        """AC: detect() returns False when no camera found."""
        manager = CameraManager()
        result = manager.detect()
        assert result is False
        assert manager.connected is False
        assert manager.camera_device is None

    def test_detect_scans_multiple_indices(self, mock_camera_at_2):
        """AC: detect() scans multiple indices and returns first working one."""
        manager = CameraManager()
        result = manager.detect()
        assert result is True

    def test_lazy_init_no_camera_needed(self):
        """AC: CameraManager class with lazy initialization (no camera needed at import)."""
        manager = CameraManager()
        assert manager.connected is False
        assert manager.camera_device is None


# ---------------------------------------------------------------------------
# capture() tests
# ---------------------------------------------------------------------------


class TestCapture:
    """Tests for CameraManager.capture()."""

    def test_capture_returns_jpeg_bytes(self, mock_camera_at_0):
        """AC: capture(max_width=1280) returns JPEG bytes resized to max_width."""
        manager = CameraManager()
        manager.detect()
        result = manager.capture(max_width=1280)
        assert isinstance(result, bytes)
        assert len(result) > 0
        # JPEG magic bytes
        assert result[:2] == b"\xff\xd8"

    def test_capture_resizes_to_max_width(self, mock_camera_at_0):
        """AC: capture() resizes to max_width."""
        manager = CameraManager()
        manager.detect()
        result = manager.capture(max_width=640)
        assert isinstance(result, bytes)
        assert len(result) > 0
        # Decode to verify dimensions
        import cv2

        buf = cv2.imdecode(np.frombuffer(result, np.uint8), cv2.IMREAD_COLOR)
        assert buf.shape[1] <= 640

    def test_capture_raises_when_no_camera(self, mock_no_camera):
        """AC: capture() raises/returns error when camera unavailable."""
        manager = CameraManager()
        with pytest.raises(CameraError):
            manager.capture()

    def test_capture_reconnects_on_disconnect(self, mock_camera_at_0):
        """AC: capture() handles camera disconnect and reopens on next call."""
        frame = _make_frame()
        read_count = 0

        class VC:
            def __init__(self, device):
                self.opened = _device_index(device) == 0

            def isOpened(self):  # noqa: N802
                return self.opened

            def read(self):
                nonlocal read_count
                if not self.opened:
                    return False, None
                read_count += 1
                # First read succeeds, then simulate disconnect
                if read_count == 1:
                    self.opened = False
                    return True, frame.copy()
                # After reconnect, read fails (no more frames)
                return False, None

            def grab(self):
                return self.opened

            def release(self):
                self.opened = False

            def get(self, prop_id):
                return 0.0

            def set(self, prop_id, value):
                return True

        with patch("cv2.VideoCapture", VC):
            manager = CameraManager()
            manager.detect()
            # First capture succeeds (frame before disconnect)
            result1 = manager.capture()
            assert result1[:2] == b"\xff\xd8"

            # After the read, camera handle is invalid (opened=False)
            # Manager should try to reconnect (create new VC(0) which opens)
            # But the new instance's read() returns False (read_count > 1)
            # So it should raise CameraError
            with pytest.raises(CameraError):
                manager.capture()

    def test_handle_released_on_exception(self, mock_camera_at_0):
        """AC: camera handle is released on exception (no leak)."""
        frame = _make_frame()
        read_count = 0
        handles = []

        class VC:
            def __init__(self, device):
                self.opened = _device_index(device) == 0
                handles.append(self)

            def isOpened(self):  # noqa: N802
                return self.opened

            def read(self):
                nonlocal read_count
                read_count += 1
                if read_count == 1:
                    return True, frame.copy()
                # Second read raises an exception
                raise RuntimeError("hardware error")

            def grab(self):
                return self.opened

            def release(self):
                self.opened = False

            def get(self, prop_id):
                return 0.0

            def set(self, prop_id, value):
                return True

        with patch("cv2.VideoCapture", VC):
            manager = CameraManager()
            manager.detect()
            # First capture succeeds
            manager.capture()
            # Second capture raises exception (read fails)
            with pytest.raises(CameraError):
                manager.capture()

            # The handle used during detect should have been released
            assert handles[0].isOpened() is False


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestConfig:
    """Tests for config module."""

    def test_default_values(self):
        """AC: Default values for settings."""
        from camera_mcp.config import Settings

        s = Settings()
        assert s.host == "0.0.0.0"
        assert s.port == 8579
        assert s.max_width == 1280
        assert s.jpeg_quality == 85
        assert s.log_level == "INFO"

    def test_env_var_override(self, monkeypatch):
        """AC: Settings from env vars (host, port, max_width, jpeg_quality)."""
        from camera_mcp.config import Settings

        monkeypatch.setenv("CAMERA_HOST", "127.0.0.1")
        monkeypatch.setenv("CAMERA_PORT", "9000")
        monkeypatch.setenv("CAMERA_MAX_WIDTH", "640")
        monkeypatch.setenv("CAMERA_JPEG_QUALITY", "90")
        monkeypatch.setenv("CAMERA_LOG_LEVEL", "DEBUG")

        s = Settings()
        assert s.host == "127.0.0.1"
        assert s.port == 9000
        assert s.max_width == 640
        assert s.jpeg_quality == 90
        assert s.log_level == "DEBUG"
