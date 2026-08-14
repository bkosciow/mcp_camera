"""Configuration and logging setup."""

import logging
import logging.handlers
import sys
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    host: str = Field(default="0.0.0.0", description="Listen address")
    port: int = Field(default=8579, description="Listen port")
    max_width: int = Field(default=1280, description="Default max image width (px)")
    jpeg_quality: int = Field(default=85, description="JPEG quality (1-100)")
    log_level: str = Field(default="INFO", description="Log level")

    model_config = {"env_prefix": "CAMERA_", "env_file": ".env", "extra": "ignore"}


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()


class JsonFormatter(logging.Formatter):
    """Format log records as JSON for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_data["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "exc_text") and record.exc_text:
            log_data["exc_text"] = record.exc_text
        import json

        return json.dumps(log_data)


def configure_logging(level: str = "INFO") -> None:
    """Configure root logger with JSON formatting.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.handlers = [handler]
