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
```

### Step 3: Configure Camera Device

Identify the USB camera device:

```bash
ls -la /dev/video*
# Typically /dev/video0
```

Edit `docker compose.prod.yml` and set the device passthrough:

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
docker compose -f docker compose.prod.yml ps
docker compose -f docker compose.prod.yml logs -f

# Verify health
curl http://localhost:8579/health
```

### Step 5: SSL with Traefik (Optional)

For HTTPS access, add Traefik to `docker compose.prod.yml`:

```yaml
services:
  traefik:
    image: traefik:v2.10
    command:
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
      - "--certificatesresolvers.letsencrypt.acme.email=your@email.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - letsencrypt:/letsencrypt
    restart: unless-stopped

  app:
    # Remove ports mapping when using Traefik
    # labels:
    #   - "traefik.enable=true"
    #   - "traefik.http.routers.app.rule=Host(`camera.example.com`)"
    #   - "traefik.http.routers.app.entrypoints=websecure"
    #   - "traefik.http.routers.app.tls.certresolver=letsencrypt"

volumes:
  letsencrypt:
```

## Deployment from Container Registry

Build and push image via GitHub Actions (`.github/workflows/deploy.yml`), then pull on server:

```bash
# On the server
docker login ghcr.io
docker pull ghcr.io/<owner>/camera_mcp:latest

# Update docker-compose.prod.yml to use the pulled image
# Change 'build:' to 'image:'
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
# Basic check
curl -f http://localhost:8579/health || echo "UNHEALTHY"

# Check camera status
curl -s http://localhost:8579/health | python3 -c "import sys,json; d=json.load(sys.stdin); print('Camera:', d['camera']['connected'])"
```

## Resource Limits

The production compose file sets:
- **CPU**: 1 core max
- **Memory**: 256 MB max

Adjust in `docker compose.prod.yml` under `deploy.resources.limits` if needed.
