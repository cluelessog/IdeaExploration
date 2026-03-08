from __future__ import annotations
import logging
from ideagen.core.config import ProviderConfig
from ideagen.core.exceptions import ConfigError
from ideagen.providers.base import AIProvider
from ideagen.providers.claude import ClaudeProvider

logger = logging.getLogger("ideagen")


def get_provider(config: ProviderConfig) -> AIProvider:
    """Get an AI provider based on config."""
    name = config.default

    if name == "claude":
        return ClaudeProvider(model=config.model)

    if name == "openai":
        try:
            from ideagen.providers.openai_provider import OpenAIProvider
        except ImportError:
            raise ConfigError("OpenAI provider requires: pip install ideagen[openai]")
        if not config.openai_api_key:
            raise ConfigError("OpenAI provider requires OPENAI_API_KEY environment variable")
        return OpenAIProvider(api_key=config.openai_api_key, model=config.model)

    if name == "gemini":
        try:
            from ideagen.providers.gemini import GeminiProvider
        except ImportError:
            raise ConfigError("Gemini provider requires: pip install ideagen[gemini]")
        if not config.gemini_api_key:
            raise ConfigError("Gemini provider requires GEMINI_API_KEY environment variable")
        return GeminiProvider(api_key=config.gemini_api_key, model=config.model)

    raise ConfigError(f"Unknown provider: {name}. Available: claude, openai, gemini")
