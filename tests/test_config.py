"""Tests for OpenCode settings without reading developer credentials."""

import pytest
from pydantic import ValidationError

from credit_agreement_extractor.config import OpenCodeSettings


def test_defaults_do_not_require_live_credentials() -> None:
    settings = OpenCodeSettings(_env_file=None)

    assert settings.api_key is None
    assert settings.model is None
    assert str(settings.base_url) == "https://opencode.ai/zen/v1"
    assert settings.api_style == "responses"


def test_live_validation_names_missing_settings() -> None:
    settings = OpenCodeSettings(_env_file=None)

    with pytest.raises(ValueError, match="OPENCODE_API_KEY, OPENCODE_MODEL"):
        settings.require_live_credentials()


def test_api_key_is_masked_in_repr() -> None:
    settings = OpenCodeSettings(
        _env_file=None,
        api_key="opencode-secret-value",
        model="gpt-5.6-luna",
    )

    assert "opencode-secret-value" not in repr(settings)


def test_api_style_is_restricted_to_supported_endpoint_shapes() -> None:
    with pytest.raises(ValidationError):
        OpenCodeSettings(_env_file=None, api_style="unknown")
