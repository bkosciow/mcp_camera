#!/bin/sh
# Start camera API server and MCP server in one container.

# Camera API server (background)
uvicorn camera_mcp.main:app \
  --host "${CAMERA_HOST:-0.0.0.0}" \
  --port "${CAMERA_PORT:-8579}" &
API_PID=$!

# MCP server (background)
camera-mcp-mcp &
MCP_PID=$!

# Graceful shutdown — kill both children on exit
trap 'kill $API_PID $MCP_PID 2>/dev/null' EXIT

# Wait for either to exit
wait
