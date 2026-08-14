FROM python:3.12-slim

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
RUN uv sync --frozen --no-install-project

# Create non-root user
RUN groupadd --gid 1001 appuser && \
    useradd --uid 1001 --gid appuser --shell /bin/sh appuser

# Copy application code and install project (entry points)
COPY --chown=appuser:appuser src/ ./src/
RUN uv sync --frozen

COPY .docker/start.sh /app/start.sh
RUN chmod +x /app/start.sh

USER appuser

EXPOSE 8579 8580

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8579/health || exit 1

ENTRYPOINT ["/app/start.sh"]
