# Deployment Guide

## VPS Deployment (Docker Compose)

### Prerequisites

- Ubuntu 24.04 LTS server (x86_64) with attached USB camera
- Docker & Docker Compose v2
- SSH access

### Step 1: Prepare Server

```bash
# SSH into server
ssh user@your-server

# Install Docker (if not installed)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
```

### Step 2: Clone and Configure

```bash
# Clone repository
git clone <repo-url>
cd camera_mcp

# Create production environment
cp .env.example .env
```

Edit `.env` with production values:

```bash
CAMERA_HOST=0.0.0.0
CAMERA_PORT=8579
CAMERA_MAX_WIDTH=1280
CAMERA_JPEG_QUALITY=85
CAMERA_LOG_LEVEL=INFO
MCP_PORT=8580
# Location name(s) for this deployment; 'default' marks the place used when
# a location is not specified, e.g. CAMERA_PLACES=default,home or office
CAMERA_PLACES=default
```

Generate both tokens and append them to `.env` — the app refuses to start without either:

```bash
python3 -c 'import secrets; print("CAMERA_AUTH_TOKEN=" + secrets.token_hex(32))' >> .env
python3 -c 'import secrets; print("MCP_AUTH_TOKEN=" + secrets.token_hex(32))' >> .env
```

`docker-compose.prod.yml` passes both from `.env` into the container and fails fast if either is missing.

### Step 3: Configure Camera Device

Identify the USB camera device:

```bash
ls -la /dev/video*
# Typically /dev/video0
```

Edit `docker-compose.prod.yml` and set the device passthrough:

```yaml
devices:
  - "/dev/video0:/dev/video0"
```

Or set via environment:

```bash
export CAMERA_DEVICE=/dev/video0
```

### Step 4: Deploy

```bash
# Build and start
make prod-up

# Check status
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f

# Verify health
curl http://localhost:8579/health
```

## Maintenance

```bash
# View logs
make prod-logs

# Restart
make prod-restart

# Update and rebuild
git pull
make prod-up

# Stop
make prod-down
```

## Health Monitoring

```bash
# Camera API health
curl -f http://localhost:8579/health || echo "UNHEALTHY"

# MCP server check (401 = up and requiring auth; anything else is a problem)
code=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8580/mcp)
[ "$code" = "401" ] || echo "MCP UNHEALTHY (got $code)"

# Check camera status
curl -s http://localhost:8579/health | python3 -c "import sys,json; d=json.load(sys.stdin); print('Camera:', d['camera']['connected'])"
```

## Resource Limits

The production compose file sets:
- **CPU**: 1 core max
- **Memory**: 256 MB max

Adjust in `docker-compose.prod.yml` under `deploy.resources.limits` if needed.

## External MCP Consumer

The MCP server listens on port 8580 using the **streamable-http** transport. An external container (e.g., Claude Code, LangChain) connects as an MCP client to:

```
http://<camera-host>:8580/mcp
```

Every request must carry the MCP bearer token:

```
Authorization: Bearer <MCP_AUTH_TOKEN>
```

Claude Code `.mcp.json` example (env interpolation keeps the literal secret out of the file):

```json
{
  "mcpServers": {
    "camera": {
      "url": "http://<camera-host>:8580/mcp",
      "headers": { "Authorization": "Bearer ${MCP_AUTH_TOKEN}" }
    }
  }
}
```

If running both containers in a Docker network, use the service name:

```python
# Example: MCP client in another container
# Must send: Authorization: Bearer <MCP_AUTH_TOKEN>
mcp_client.connect("http://camera-mcp:8580/mcp")
```

For local development with Claude Code subprocess, override the transport:

```bash
MCP_TRANSPORT=stdio uv run camera-mcp-mcp
```
