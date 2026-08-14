FROM python:3.14-slim

WORKDIR /app

# System dependencies for OpenCV
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies
RUN uv venv /app/.venv
ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

COPY pyproject.toml uv.lock ./
COPY src/ ./src/

RUN uv sync --frozen

# Create non-root user with video group for /dev/video* access
# GID 44 matches the standard 'video' group on most Linux distros
RUN groupadd --gid 1001 appuser && \
    groupadd -g 44 -o video 2>/dev/null || true && \
    useradd --uid 1001 --gid appuser --groups video --shell /bin/sh appuser

COPY .docker/start.sh /app/start.sh
RUN chmod +x /app/start.sh

USER appuser

EXPOSE 8579 8580

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8579/health || exit 1

ENTRYPOINT ["/app/start.sh"]
