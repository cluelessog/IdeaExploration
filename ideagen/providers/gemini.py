"""Google Gemini provider (optional). Requires: pip install ideagen[gemini]"""

from __future__ import annotations

import logging
from typing import TypeVar

from pydantic import BaseModel

from ideagen.core.exceptions import ConfigError, ProviderError
from ideagen.providers.base import AIProvider
from ideagen.utils.text import extract_json

logger = logging.getLogger("ideagen")
T = TypeVar("T", bound=BaseModel)


class GeminiProvider(AIProvider):
    """AI provider using the Google GenAI SDK."""

    def __init__(self, api_key: str, model: str | None = None):
        try:
            import google.genai  # noqa: F401
        except ImportError:
            raise ConfigError(
                "Gemini provider requires the google-genai package. "
                "Install with: pip install ideagen[gemini]"
            )
        self._api_key = api_key
        self._model = model or "gemini-2.0-flash"

    async def complete(
        self,
        user_prompt: str,
        response_type: type[T],
        system_prompt: str | None = None,
    ) -> T:
        try:
            from google import genai
        except ImportError:
            raise ConfigError("Google GenAI package not installed: pip install ideagen[gemini]")

        # Schema is already embedded by prompts.py (single source of truth); pass prompt through as-is
        parts = []
        if system_prompt:
            parts.append(system_prompt)
        parts.append(user_prompt)
        full_prompt = "\n\n".join(parts)

        try:
            client = genai.Client(api_key=self._api_key)
            response = await client.aio.models.generate_content(
                model=self._model,
                contents=full_prompt,
            )
            raw_text = response.text or ""
        except Exception as e:
            raise ProviderError(f"Gemini API error: {e}")

        try:
            raw_json = extract_json(raw_text)
        except ValueError as e:
            raise ProviderError(f"Failed to extract JSON from Gemini response: {e}")

        return response_type.model_validate_json(raw_json)
