"""Shared test fixtures."""

import os

import pytest

# camera_mcp.main builds a module-level app at import time, and create_app()
# refuses to start without an auth token. Set a known value before any test
# module imports it. (Env vars override the .env file, keeping tests deterministic.)
os.environ["CAMERA_AUTH_TOKEN"] = "test-token"
# Pin places too, so a developer's .env CAMERA_PLACES can't leak into tests.
os.environ["CAMERA_PLACES"] = "default"


@pytest.fixture(autouse=True)
def reset_camera_manager():
    """Reset CameraManager singleton before and after each test."""
    from camera_mcp.camera import CameraManager

    CameraManager.reset()
    yield
    CameraManager.reset()
