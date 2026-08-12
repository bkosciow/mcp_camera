# Camera MCP — Agent Instructions

## Project Overview

USB camera snapshot service that captures fresh images from an attached USB camera and serves them via a simple HTTP API. An optional MCP server exposes camera tools to Claude Code for live image capture.

**Core value**: Every API call captures a new frame — no stale caches, no pre-recorded footage.

## Tech Stack

- **Python 3.12+** with `uv` (package manager)
- **FastAPI** for the HTTP layer
- **OpenCV (cv2)** for camera capture and image processing
- **uvicorn** ASGI server
- **pydantic-settings** for configuration
- **pytest** for testing (all tests mock `cv2.VideoCapture` — no hardware needed)
- **ruff** for linting, **mypy** for type checking

## Architecture

Single-container stateless service with three components:

### 1. Camera Manager (`src/camera_mcp/camera.py`)

Singleton that handles USB camera detection, capture, and auto-reconnection. Scans `/dev/video*` devices first, then falls back to indices 0–5. Configures highest native resolution (1920×1080 → 1280×720 fallback). Discards stale buffered frames before each capture for freshness.

### 2. HTTP API (`src/camera_mcp/main.py`)

FastAPI application with three endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/capture` | GET | Capture a fresh JPEG image (resizable via `max_width` query param, 160–3840px) |
| `/camera` | GET | Camera info and available resolutions |
| `/health` | GET | Service health, camera connection state, uptime, last error |

### 3. MCP Server (`src/camera_mcp/mcp_server.py`)

Model Context Protocol server exposing two tools for Claude Code:

- **`capture_image(max_width)`** — calls the running `/capture` endpoint, returns the JPEG as an `Image` object
- **`camera_status()`** — calls `/health`, returns formatted status string

The MCP server connects to the camera API via HTTP (configured via `CAMERA_API_URL` env var, defaults to `http://localhost:8579`). It does NOT import the camera module directly — it's a thin HTTP client over the running API.

## Configuration

Environment variables are read via `pydantic-settings` with prefix `CAMERA_`:

| Variable | Default | Description |
|----------|---------|-------------|
| `CAMERA_HOST` | `0.0.0.0` | Listen address |
| `CAMERA_PORT` | `8579` | Listen port |
| `CAMERA_MAX_WIDTH` | `1280` | Default max image width (px) |
| `CAMERA_JPEG_QUALITY` | `85` | JPEG quality (1–100) |
| `CAMERA_LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |
| `CAMERA_API_URL` | `http://localhost:8579` | Camera API URL for MCP server |

## Development Commands

```bash
# Start development server
make dev
# or
uv run uvicorn src.camera_mcp.main:app --host 0.0.0.0 --port 8579 --reload

# Run MCP server standalone
uv run camera-mcp-mcp

# Testing
make test          # All tests
make test-unit     # Unit tests only
make test-coverage # With coverage report

# Linting and type checking
uv run ruff check .
uv run mypy src/
```

## Docker

```bash
# Development with Docker
make dev-docker    # docker compose up

# Production build
make prod          # docker compose -f docker-compose.prod.yml up --build
```

Camera device is passed through via `--device /dev/video0` in Docker Compose.

## Testing Conventions

- All tests mock `cv2.VideoCapture` — no hardware required
- Use `pytest-asyncio` with `auto` mode
- Test structure: `tests/unit/` for isolated tests, `tests/integration/` for API-level tests
- Fixtures in `tests/conftest.py` provide mocked camera and test client

## Code Style

- **Strict mypy** — all code must be fully typed
- **ruff** — E, F, I, N, W, UP rules enabled
- **Line length**: 100
- **Target Python**: 3.12
- Follow existing patterns in `camera.py` and `main.py` for new code

## Deployment

See `DEPLOYMENT.md` for production deployment guide. The service is stateless — scale horizontally with multiple containers if needed (each needs its own camera device).
