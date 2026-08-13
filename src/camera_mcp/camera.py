"""Camera detection, capture, and reconnection logic."""

import logging
from pathlib import Path

import cv2

logger = logging.getLogger(__name__)


class CameraError(Exception):
    """Raised when camera capture fails."""


class SingleCamera:
    """Manages a single USB camera handle.

    Handles detection, capture, auto-reconnection, and resolution probing
    for one camera device.
    """

    def __init__(self, device: int | str) -> None:
        self._device = device
        self._handle: cv2.VideoCapture | None = None
        self._connected: bool = False
        self._last_error: str | None = None

    @property
    def device(self) -> int | str | None:
        """The camera device index or path."""
        return self._device

    @property
    def connected(self) -> bool:
        """Whether this camera is currently connected."""
        return self._connected

    @property
    def last_error(self) -> str | None:
        """The last error message, if any."""
        return self._last_error

    def _handle_valid(self) -> bool:
        """Check if the current camera handle is open and usable."""
        return self._handle is not None and self._handle.isOpened()

    def _configure_handle(self, handle: cv2.VideoCapture) -> None:
        """Minimize capture latency and set highest native resolution."""
        handle.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        # Set camera to highest supported resolution for best quality
        handle.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        handle.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        # If not supported, try 1280x720
        actual_w = handle.get(cv2.CAP_PROP_FRAME_WIDTH)
        if actual_w < 1280:
            handle.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            handle.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    def open(self) -> bool:
        """Try to open this camera device.

        Returns:
            True if the camera was successfully opened.
        """
        handle = cv2.VideoCapture(self._device)
        if handle.isOpened():
            self._configure_handle(handle)
            self._handle = handle
            self._connected = True
            self._last_error = None
            logger.info("Camera opened: %s", self._device)
            return True

        self._connected = False
        self._last_error = f"Failed to open camera: {self._device}"
        return False

    def capture(self, max_width: int = 1280) -> bytes:
        """Capture a frame and return it as JPEG bytes resized to max_width.

        If the camera handle is invalid, attempts to reconnect before capturing.

        Args:
            max_width: Maximum image width in pixels (default 1280).

        Returns:
            JPEG-encoded image bytes.

        Raises:
            CameraError: If no camera is available.
        """
        # Reconnect if handle is invalid
        if not self._handle_valid():
            if not self.open():
                self._last_error = "Camera not connected"
                raise CameraError(self._last_error)

        try:
            # Ensure we get the freshest frame — discard stale buffered frames
            if self._handle is not None and self._handle.isOpened():
                for _ in range(3):
                    self._handle.grab()

            if not self._handle_valid():
                if not self.open():
                    raise CameraError("Camera not connected")

            assert self._handle is not None
            success, frame = self._handle.read()
            if not success:
                raise ValueError("Failed to read frame")

            height, width = frame.shape[:2]
            if width > max_width:
                scale = max_width / width
                new_width = int(width * scale)
                new_height = int(height * scale)
                frame = cv2.resize(frame, (new_width, new_height))

            _, buf = cv2.imencode(".jpg", frame)
            return buf.tobytes()

        except CameraError:
            raise
        except Exception as exc:
            self._last_error = str(exc)
            if self._handle is not None:
                self._handle.release()
                self._handle = None
            logger.error("Capture failed on %s: %s", self._device, exc)
            raise CameraError(str(exc)) from exc

    def release(self) -> None:
        """Release the camera handle."""
        if self._handle is not None:
            self._handle.release()
            self._handle = None
            self._connected = False

    def current_resolution(self) -> tuple[int, int]:
        """Return the camera's native (WxH) resolution."""
        if self._handle is None or not self._handle.isOpened():
            return (0, 0)
        width = self._handle.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = self._handle.get(cv2.CAP_PROP_FRAME_HEIGHT)
        return (int(width), int(height))

    PROBE_RESOLUTIONS: list[tuple[int, int]] = [
        (640, 480),
        (800, 600),
        (1024, 768),
        (1280, 720),
        (1280, 960),
        (1600, 1200),
        (1920, 1080),
        (2560, 1440),
        (3840, 2160),
    ]

    def available_resolutions(self) -> list[tuple[int, int]]:
        """Probe the camera to find which resolutions it actually supports.

        Tries each standard resolution, checks if the camera accepted it,
        then restores the original resolution.
        """
        if self._handle is None or not self._handle.isOpened():
            return []

        orig_w = self._handle.get(cv2.CAP_PROP_FRAME_WIDTH)
        orig_h = self._handle.get(cv2.CAP_PROP_FRAME_HEIGHT)
        supported: list[tuple[int, int]] = []

        for w, h in self.PROBE_RESOLUTIONS:
            self._handle.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            self._handle.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            actual_w = self._handle.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_h = self._handle.get(cv2.CAP_PROP_FRAME_HEIGHT)
            if abs(actual_w - w) < 1 and abs(actual_h - h) < 1:
                supported.append((w, h))

        # Restore original
        self._handle.set(cv2.CAP_PROP_FRAME_WIDTH, orig_w)
        self._handle.set(cv2.CAP_PROP_FRAME_HEIGHT, orig_h)
        return supported


class CameraManager:
    """Manages multiple USB cameras.

    Scans for available cameras and provides indexed access.
    Uses lazy initialization — no camera is required at construction time.
    """

    _instance: "CameraManager | None" = None

    def __new__(cls) -> "CameraManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._cameras: list[SingleCamera] = []

    @classmethod
    def reset(cls) -> None:
        """Reset singleton state. Intended for testing only."""
        if cls._instance is not None:
            for camera in cls._instance._cameras:
                camera.release()
            cls._instance._cameras = []
        cls._instance = None

    def detect(self) -> int:
        """Scan for available cameras and open all found.

        Checks /dev/video* devices first, then falls back to indices 0-5.

        Returns:
            The number of cameras detected.
        """
        self._cameras = []
        found_devices: list[int | str] = []

        # Try /dev/video* devices first
        if Path("/dev").exists():
            video_devices = sorted(Path("/dev").glob("video*"))
            for video_path in video_devices:
                handle = cv2.VideoCapture(str(video_path))
                if handle.isOpened():
                    handle.release()
                    found_devices.append(str(video_path))

        # Fallback: try indices 0-5 (only if no /dev/video* found)
        if not found_devices:
            for index in range(6):
                handle = cv2.VideoCapture(index)
                if handle.isOpened():
                    handle.release()
                    found_devices.append(index)

        # Create SingleCamera instances for each found device
        for dev in found_devices:
            camera = SingleCamera(dev)
            if camera.open():
                self._cameras.append(camera)

        logger.info("Detected %d camera(s)", len(self._cameras))
        return len(self._cameras)

    @property
    def count(self) -> int:
        """Number of detected cameras."""
        return len(self._cameras)

    @property
    def connected(self) -> bool:
        """Whether at least one camera is connected."""
        return len(self._cameras) > 0

    @property
    def camera_device(self) -> int | str | None:
        """Device of the first camera (backwards compatibility)."""
        return self._cameras[0].device if self._cameras else None

    @property
    def last_error(self) -> str | None:
        """Last error from the first camera (backwards compatibility)."""
        return self._cameras[0].last_error if self._cameras else None

    def __getitem__(self, index: int) -> SingleCamera:
        """Get a camera by index.

        Args:
            index: Camera index (0-based).

        Returns:
            The SingleCamera at the given index.

        Raises:
            IndexError: If index is out of range.
        """
        return self._cameras[index]

    def get(self, index: int = 0) -> SingleCamera | None:
        """Get a camera by index, or None if out of range.

        Args:
            index: Camera index (0-based, defaults to 0).

        Returns:
            The SingleCamera at the given index, or None.
        """
        try:
            return self._cameras[index]
        except IndexError:
            return None

    def release(self) -> None:
        """Release all camera handles."""
        for camera in self._cameras:
            camera.release()
        self._cameras = []

    @property
    def cameras(self) -> list[SingleCamera]:
        """Get the list of detected cameras."""
        return list(self._cameras)

    # -- Backwards-compatible proxies to the first camera --

    def capture(self, max_width: int = 1280) -> bytes:
        """Capture from the first camera (backwards compatibility)."""
        if not self._cameras:
            raise CameraError("No camera available")
        return self._cameras[0].capture(max_width=max_width)

    def current_resolution(self) -> tuple[int, int]:
        """Current resolution of the first camera (backwards compatibility)."""
        if not self._cameras:
            return (0, 0)
        return self._cameras[0].current_resolution()

    def available_resolutions(self) -> list[tuple[int, int]]:
        """Available resolutions of the first camera (backwards compatibility)."""
        if not self._cameras:
            return []
        return self._cameras[0].available_resolutions()
