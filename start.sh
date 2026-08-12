#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

# Load .env if it exists
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/.env"
    set +a
fi

# Activate venv
if [ -d "$VENV" ]; then
    # shellcheck disable=SC1091
    source "$VENV/bin/activate"
else
    echo "❌ .venv not found. Run: uv sync"
    exit 1
fi

echo "📸 Camera MCP starting on ${CAMERA_HOST:-0.0.0.0}:${CAMERA_PORT:-8579}"

PYTHONPATH="$SCRIPT_DIR/src" exec uvicorn camera_mcp.main:app \
    --host "${CAMERA_HOST:-0.0.0.0}" \
    --port "${CAMERA_PORT:-8579}"
