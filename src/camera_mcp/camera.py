"""Camera detection, capture, and reconnection logic."""

import logging
from pathlib import Path

import cv2

logger = logging.getLogger(__name__)


class CameraError(Exception):
    """Raised when camera capture fails."""


class CameraManager:
    """Manages USB camera detection, capture, and reconnection.

    Uses lazy initialization — no camera is required at import or construction time.
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
        self._handle: cv2.VideoCapture | None = None
        self._camera_device: int | str | None = None
        self._connected: bool = False
        self._last_error: str | None = None

    @classmethod
    def reset(cls) -> None:
        """Reset singleton state. Intended for testing only."""
        if cls._instance is not None:
            if cls._instance._handle is not None:
                cls._instance._handle.release()
            cls._instance._handle = None
            cls._instance._camera_device = None
            cls._instance._connected = False
            cls._instance._last_error = None
        cls._instance = None

    @property
    def connected(self) -> bool:
        """Whether a camera was successfully detected."""
        return self._connected

    @property
    def camera_device(self) -> int | str | None:
        """The detected camera device index or path."""
        return self._camera_device

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

    def detect(self) -> bool:
        """Scan for available cameras and connect to the first one found.

        Checks /dev/video* devices first, then falls back to indices 0-5.

        Returns:
            True if a camera was found and opened, False otherwise.
        """
        # Try /dev/video* devices first
        video_devices = sorted(Path("/dev").glob("video*")) if Path("/dev").exists() else []
        for device in video_devices:
            handle = cv2.VideoCapture(str(device))
            if handle.isOpened():
                self._configure_handle(handle)
                self._handle = handle
                self._camera_device = str(device)
                self._connected = True
                self._last_error = None
                logger.info("Camera detected: %s", device)
                return True

        # Fallback: try indices 0-5
        for index in range(6):
            handle = cv2.VideoCapture(index)
            if handle.isOpened():
                self._configure_handle(handle)
                self._handle = handle
                self._camera_device = index
                self._connected = True
                self._last_error = None
                logger.info("Camera detected at index %d", index)
                return True

        self._connected = False
        self._camera_device = None
        self._last_error = "No camera found"
        logger.warning("No camera detected")
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
        # Reconnect if we have a known device but handle is invalid
        if self._camera_device is not None and not self._handle_valid():
            try:
                handle = cv2.VideoCapture(self._camera_device)
                if handle.isOpened():
                    self._configure_handle(handle)
                    self._handle = handle
                    self._connected = True
                    self._last_error = None
                    logger.info("Camera reconnected: %s", self._camera_device)
                else:
                    raise ValueError("Reconnection failed")
            except Exception as exc:
                self._connected = False
                self._last_error = str(exc)
                logger.warning("Camera reconnection failed: %s", exc)

        # Try detection if no known device
        if self._camera_device is None and not self.detect():
            self._last_error = "No camera available"
            raise CameraError("No camera available")

        if not self._connected:
            self._last_error = "Camera not connected"
            raise CameraError("Camera not connected")

        try:
            # Ensure we get the freshest frame — discard stale buffered frames
            if self._handle_valid():
                for _ in range(3):
                    self._handle.grab()

            if not self._handle_valid():
                if self._camera_device is not None:
                    new_handle = cv2.VideoCapture(self._camera_device)
                    if new_handle.isOpened():
                        self._configure_handle(new_handle)
                        self._handle = new_handle
                    else:
                        raise ValueError("Failed to open camera")
                else:
                    raise ValueError("No camera device specified")

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
            logger.error("Capture failed: %s", exc)
            raise CameraError(str(exc)) from exc

    def release(self) -> None:
        """Release the camera handle."""
        if self._handle is not None:
            self._handle.release()
            self._handle = None

    def current_resolution(self) -> tuple[int, int]:
        """Return the camera's native (WxH) resolution."""
        if not self._handle_valid():
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
        if not self._handle_valid():
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
