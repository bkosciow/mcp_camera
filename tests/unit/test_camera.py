"""Unit tests for camera module — mocked cv2, no hardware required."""

from unittest.mock import patch

import numpy as np
import pytest

from camera_mcp.camera import CameraError, CameraManager, SingleCamera


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
def mock_multi_camera():
    """Mock cv2.VideoCapture to simulate cameras at indices 0 and 2."""
    frame = _make_frame()
    openable = {0, 2}

    class VC:
        def __init__(self, device):
            self.opened = _device_index(device) in openable

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
# SingleCamera tests
# ---------------------------------------------------------------------------


class TestSingleCameraOpen:
    """Tests for SingleCamera.open()."""

    def test_open_succeeds_for_valid_device(self, mock_camera_at_0):
        cam = SingleCamera(0)
        assert cam.open() is True
        assert cam.connected is True
        assert cam.device == 0

    def test_open_fails_for_invalid_device(self, mock_camera_at_2):
        cam = SingleCamera(0)
        assert cam.open() is False
        assert cam.connected is False

    def test_open_sets_last_error_on_failure(self, mock_no_camera):
        cam = SingleCamera(0)
        cam.open()
        assert cam.last_error is not None


class TestSingleCameraCapture:
    """Tests for SingleCamera.capture()."""

    def test_capture_returns_jpeg_bytes(self, mock_camera_at_0):
        cam = SingleCamera(0)
        cam.open()
        result = cam.capture(max_width=1280)
        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result[:2] == b"\xff\xd8"

    def test_capture_resizes_to_max_width(self, mock_camera_at_0):
        cam = SingleCamera(0)
        cam.open()
        result = cam.capture(max_width=640)
        import cv2

        buf = cv2.imdecode(np.frombuffer(result, np.uint8), cv2.IMREAD_COLOR)
        assert buf.shape[1] <= 640

    def test_capture_raises_when_not_opened(self, mock_no_camera):
        cam = SingleCamera(0)
        with pytest.raises(CameraError):
            cam.capture()

    def test_capture_reconnects_on_invalid_handle(self, mock_camera_at_0):
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
            cam = SingleCamera(0)
            cam.open()
            # First capture succeeds
            result = cam.capture()
            assert result[:2] == b"\xff\xd8"

            # Simulate disconnect
            cam._handle.release()
            cam._connected = False

            # Next capture should reconnect and succeed
            result2 = cam.capture()
            assert result2[:2] == b"\xff\xd8"

    def test_release_clears_handle(self, mock_camera_at_0):
        cam = SingleCamera(0)
        cam.open()
        assert cam.connected is True
        cam.release()
        assert cam.connected is False


class TestSingleCameraResolution:
    """Tests for SingleCamera resolution methods."""

    def test_current_resolution_returns_zero_when_disconnected(self, mock_no_camera):
        cam = SingleCamera(0)
        w, h = cam.current_resolution()
        assert w == 0
        assert h == 0

    def test_available_resolutions_empty_when_disconnected(self, mock_no_camera):
        cam = SingleCamera(0)
        assert cam.available_resolutions() == []


# ---------------------------------------------------------------------------
# CameraManager tests
# ---------------------------------------------------------------------------


class TestManagerDetect:
    """Tests for CameraManager.detect()."""

    def test_detect_finds_single_camera(self, mock_camera_at_0):
        manager = CameraManager()
        count = manager.detect()
        assert count == 1
        assert manager.connected is True
        assert manager.count == 1

    def test_detect_returns_zero_when_no_camera(self, mock_no_camera):
        manager = CameraManager()
        count = manager.detect()
        assert count == 0
        assert manager.connected is False

    def test_detect_finds_multiple_cameras(self, mock_multi_camera):
        manager = CameraManager()
        count = manager.detect()
        assert count == 2
        assert manager.count == 2

    def test_lazy_init_no_camera_needed(self):
        manager = CameraManager()
        assert manager.connected is False
        assert manager.count == 0


class TestManagerAccess:
    """Tests for CameraManager indexed access."""

    def test_get_first_camera(self, mock_camera_at_0):
        manager = CameraManager()
        manager.detect()
        cam = manager.get(0)
        assert cam is not None
        assert cam.connected is True

    def test_get_out_of_range_returns_none(self, mock_camera_at_0):
        manager = CameraManager()
        manager.detect()
        cam = manager.get(5)
        assert cam is None

    def test_getitem_raises_on_out_of_range(self, mock_camera_at_0):
        manager = CameraManager()
        manager.detect()
        with pytest.raises(IndexError):
            _ = manager[5]

    def test_multi_camera_access(self, mock_multi_camera):
        manager = CameraManager()
        manager.detect()
        cam0 = manager.get(0)
        cam1 = manager.get(1)
        assert cam0 is not None
        assert cam0.connected is True
        assert cam1 is not None
        assert cam1.connected is True

    def test_cameras_list(self, mock_multi_camera):
        manager = CameraManager()
        manager.detect()
        cams = manager.cameras
        assert len(cams) == 2


class TestManagerBackwardsCompat:
    """Tests for backwards-compatible proxy methods on CameraManager."""

    def test_capture_delegates_to_first(self, mock_camera_at_0):
        manager = CameraManager()
        manager.detect()
        result = manager.capture(max_width=640)
        assert isinstance(result, bytes)
        assert result[:2] == b"\xff\xd8"

    def test_capture_raises_when_no_camera(self, mock_no_camera):
        manager = CameraManager()
        manager.detect()
        with pytest.raises(CameraError):
            manager.capture()

    def test_current_resolution_delegates(self, mock_camera_at_0):
        manager = CameraManager()
        manager.detect()
        w, h = manager.current_resolution()
        # Mock returns 0.0 for all props
        assert isinstance(w, int)

    def test_available_resolutions_delegates(self, mock_camera_at_0):
        manager = CameraManager()
        manager.detect()
        result = manager.available_resolutions()
        assert isinstance(result, list)

    def test_camera_device_delegates(self, mock_camera_at_0):
        manager = CameraManager()
        manager.detect()
        # detect() scans /dev/video* first, so device is "/dev/video0" (string)
        assert manager.camera_device is not None

    def test_last_error_delegates(self, mock_camera_at_0):
        manager = CameraManager()
        manager.detect()
        assert manager.last_error is None


class TestManagerRelease:
    """Tests for CameraManager.release()."""

    def test_release_clears_all_cameras(self, mock_multi_camera):
        manager = CameraManager()
        manager.detect()
        assert manager.count == 2
        manager.release()
        assert manager.count == 0


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
