"""Shared test fixtures."""

import pytest


@pytest.fixture(autouse=True)
def reset_camera_manager():
    """Reset CameraManager singleton before and after each test."""
    from camera_mcp.camera import CameraManager

    CameraManager.reset()
    yield
    CameraManager.reset()
