"""Environment-backed credentials/configuration for the shared OpenCode client.

Loading settings is separate from running the scaffold pipeline. This lets the
conversion and scaffold functions work without credentials,
and ``SecretStr`` prevents accidental key disclosure in logs and tracebacks.
"""

from enum import StrEnum

from pydantic import AnyHttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiStyle(StrEnum):
    """Endpoint shapes currently documented by OpenCode Zen."""

    RESPONSES = "responses"
    CHAT_COMPLETIONS = "chat_completions"
    MESSAGES = "messages"


class OpenCodeSettings(BaseSettings):
    """OpenCode credentials and endpoint selection loaded from ``.env``."""

    # The prefix maps ``api_key`` to ``OPENCODE_API_KEY`` and applies the same
    # convention to every provider setting. Unknown variables are ignored so a
    # project-level .env may safely hold unrelated configuration later.
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="OPENCODE_",
        extra="ignore",
    )

    api_key: SecretStr | None = None
    model: str | None = None
    base_url: AnyHttpUrl = AnyHttpUrl("https://opencode.ai/zen/v1")
    api_style: ApiStyle = ApiStyle.RESPONSES

    def require_live_credentials(self) -> None:
        """Fail clearly only when a caller requests live model access."""
        missing: list[str] = []
        if self.api_key is None:
            missing.append("OPENCODE_API_KEY")
        if not self.model:
            missing.append("OPENCODE_MODEL")
        if missing:
            raise ValueError(f"Missing live OpenCode settings: {', '.join(missing)}")
