"""Configuration and logging setup."""

import logging
import logging.handlers
import re
import sys
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode

PLACE_TOKEN_RE = re.compile(r"^[a-z0-9]+([_-][a-z0-9]+)*$")


class Settings(BaseSettings):
    """Application configuration from environment variables."""

    host: str = Field(default="0.0.0.0", description="Listen address")
    port: int = Field(default=8579, description="Listen port")
    max_width: int = Field(default=1280, description="Default max image width (px)")
    jpeg_quality: int = Field(default=85, description="JPEG quality (1-100)")
    log_level: str = Field(default="INFO", description="Log level")
    auth_token: str | None = Field(default=None, description="Bearer token required for API access")
    # NoDecode: env values are comma-separated strings, not JSON —
    # _parse_places (below) does the decoding.
    places: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["default"],
        description="Location names/aliases for this deployment, e.g. 'default,home'",
    )

    model_config = {"env_prefix": "CAMERA_", "env_file": ".env", "extra": "ignore"}

    @field_validator("places", mode="before")
    @classmethod
    def _parse_places(cls, value: object) -> object:
        """Parse a comma-separated place list (e.g. ``CAMERA_PLACES=default,home``).

        Strips whitespace, drops empty entries, deduplicates (order preserved),
        and validates each token against ``PLACE_TOKEN_RE``. An empty result
        falls back to ``["default"]``.
        """
        if isinstance(value, str):
            value = [token.strip() for token in value.split(",") if token.strip()]
        if not isinstance(value, list) or not all(isinstance(token, str) for token in value):
            raise ValueError("places must be a comma-separated string or list of strings")
        parsed: list[str] = []
        for token in value:
            if not PLACE_TOKEN_RE.fullmatch(token):
                raise ValueError(
                    f"invalid place name {token!r} — use lowercase letters, digits, '-' or '_'"
                )
            if token not in parsed:
                parsed.append(token)
        return parsed or ["default"]

    @property
    def place_name(self) -> str:
        """Display name: first alias other than ``default``, else the first alias."""
        for place in self.places:
            if place != "default":
                return place
        return self.places[0]

    @property
    def is_default_place(self) -> bool:
        """True when this deployment may be used without an explicit location."""
        return "default" in self.places


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
