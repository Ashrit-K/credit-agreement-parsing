"""LLM configuration — scaffold for v2."""

import os
from dotenv import load_dotenv

load_dotenv()

LLM_PROVIDERS = {
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4",
    },
    "anthropic": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-4-20250514",
    },
}


def get_api_key(provider: str) -> str:
    """Get API key for the given provider from environment."""
    config = LLM_PROVIDERS.get(provider, {})
    env_var = config.get("api_key_env", "")
    return os.getenv(env_var, "")


def is_llm_available(provider: str = "openai") -> bool:
    """Check if an LLM provider is configured."""
    return bool(get_api_key(provider))
