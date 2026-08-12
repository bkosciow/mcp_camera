# Camera MCP

Lightweight USB camera snapshot service. Captures fresh images from an attached USB camera and serves them via a simple HTTP API.

**Core value**: Every API call captures a new frame — no stale caches, no pre-recorded footage.

## Quick Start

### Prerequisites

- Docker & Docker Compose v2
- Python 3.12+ with `uv` (for local development without Docker)
- USB camera attached to the host

### Development

```bash
# Clone and enter
cd camera_mcp

# Copy environment file
cp .env.example .env

# Start with Docker
make dev

# Or run locally
uv sync --group dev
uv run uvicorn src.camera_mcp.main:app --host 0.0.0.0 --port 8579 --reload
```

Open [http://localhost:8579/health](http://localhost:8579/health) to verify.

### Running Tests

```bash
make test          # All tests
make test-unit     # Unit tests only
make test-coverage # With coverage report
```

All tests run without hardware — `cv2.VideoCapture` is mocked.

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/capture` | GET | Capture a fresh JPEG image from the USB camera |
| `/camera` | GET | Camera info and available resolutions |
| `/health` | GET | Service health and camera status |

### Capture

```bash
# Default (1280px max width)
curl http://localhost:8579/capture > photo.jpg

# Custom width
curl "http://localhost:8579/capture?max_width=640" > photo.jpg
```

Returns `image/jpeg` on success (200) or JSON error (503) if camera is unavailable.

### Health

```bash
curl http://localhost:8579/health
```

```json
{
  "status": "ok",
  "camera": { "connected": true, "device": 0 },
  "uptime_seconds": 1234.5,
  "last_error": null
}
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CAMERA_HOST` | `0.0.0.0` | Listen address |
| `CAMERA_PORT` | `8579` | Listen port |
| `CAMERA_MAX_WIDTH` | `1280` | Default max image width (px) |
| `CAMERA_JPEG_QUALITY` | `85` | JPEG quality (1-100) |
| `CAMERA_LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |

See `.env.example` for all options.

## Architecture

Single-container stateless service:
- **FastAPI** for the HTTP layer
- **OpenCV (cv2)** for camera capture and image processing
- **No database** — each request is independent
- Camera auto-detected on startup, auto-reconnects on disconnect

## Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for production deployment guide.

## MCP Server

The project includes an MCP server that exposes camera tools to Claude Code. When the camera API is running, Claude can capture live images and check camera status.

### Available Tools

- **`capture_image`** — Capture a fresh JPEG image from the USB camera
- **`camera_status`** — Check camera health and connection status

### Setup

1. Start the camera API service:
   ```bash
   make dev
   # or
   uv run uvicorn src.camera_mcp.main:app --host 0.0.0.0 --port 8579
   ```

2. Open Claude Code in this project directory — the MCP server is configured via `.mcp.json` and will be available automatically.

3. Use natural language to interact with the camera:
   - "can you see?" → calls `camera_status`
   - "what do you see?" → calls `capture_image`
   - "take a photo" → calls `capture_image`

### Standalone

Run the MCP server manually:
```bash
uv run camera-mcp-mcp
```

## Tech Stack

Python 3.12, FastAPI, OpenCV, uvicorn, uv (package manager), ruff, mypy, pytest.
