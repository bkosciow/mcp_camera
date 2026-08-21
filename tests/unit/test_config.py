"""Tests for CAMERA_PLACES parsing and place helpers on Settings."""

import pytest
from pydantic import ValidationError

from camera_mcp.config import Settings


def _settings(places: object) -> Settings:
    return Settings(_env_file=None, auth_token="test-token", places=places)


class TestPlacesParsing:
    """CAMERA_PLACES is a comma-separated list of location names/aliases."""

    def test_defaults_to_default_when_unset(self):
        settings = Settings(_env_file=None, auth_token="test-token")
        assert settings.places == ["default"]

    def test_parses_comma_separated_string(self):
        assert _settings("default,home").places == ["default", "home"]

    def test_strips_whitespace(self):
        assert _settings(" home , office ").places == ["home", "office"]

    def test_drops_empty_entries(self):
        assert _settings("home,,office,").places == ["home", "office"]

    def test_deduplicates_preserving_order(self):
        assert _settings("home,office,home").places == ["home", "office"]

    def test_empty_string_falls_back_to_default(self):
        assert _settings("").places == ["default"]

    def test_single_default(self):
        assert _settings("default").places == ["default"]

    def test_accepts_list_input(self):
        assert _settings(["office", "home"]).places == ["office", "home"]

    def test_parses_from_environment_variable(self, monkeypatch):
        # Regression: env values must not go through JSON decoding (NoDecode).
        monkeypatch.setenv("CAMERA_PLACES", "default,bielsko")
        settings = Settings(_env_file=None)
        assert settings.places == ["default", "bielsko"]
        assert settings.place_name == "bielsko"
        assert settings.is_default_place is True

    def test_parses_from_dotenv_file(self, tmp_path, monkeypatch):
        # Env vars take precedence over dotenv — remove the one pinned in conftest.
        monkeypatch.delenv("CAMERA_PLACES", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("CAMERA_PLACES=default,bielsko\n")
        settings = Settings(_env_file=env_file)
        assert settings.places == ["default", "bielsko"]

    @pytest.mark.parametrize(
        "value",
        [
            "Home",  # uppercase
            "has space",
            "-leading-dash",
            "_leading-underscore",
            "trailing-",
            "double--dash",
            "a/b",
        ],
    )
    def test_rejects_invalid_tokens(self, value):
        with pytest.raises(ValidationError, match="invalid place name"):
            _settings(value)


class TestPlaceHelpers:
    """place_name / is_default_place derive display info from places."""

    def test_place_name_prefers_non_default_alias(self):
        assert _settings("default,home").place_name == "home"

    def test_place_name_falls_back_to_first(self):
        assert _settings("default").place_name == "default"

    def test_is_default_true_when_default_in_names(self):
        assert _settings("default,home").is_default_place is True

    def test_is_default_false_without_default(self):
        assert _settings("office").is_default_place is False
