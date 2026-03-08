"""OpenAI provider (optional). Requires: pip install ideagen[openai]"""

from __future__ import annotations

import json
import logging
from typing import TypeVar

from pydantic import BaseModel

from ideagen.core.exceptions import ConfigError, ProviderError
from ideagen.providers.base import AIProvider
from ideagen.utils.text import extract_json

logger = logging.getLogger("ideagen")
T = TypeVar("T", bound=BaseModel)


class OpenAIProvider(AIProvider):
    """AI provider using the OpenAI SDK."""

    def __init__(self, api_key: str, model: str | None = None):
        try:
            import openai  # noqa: F401
        except ImportError:
            raise ConfigError(
                "OpenAI provider requires the openai package. "
                "Install with: pip install ideagen[openai]"
            )
        self._api_key = api_key
        self._model = model or "gpt-4o"

    async def complete(
        self,
        user_prompt: str,
        response_type: type[T],
        system_prompt: str | None = None,
    ) -> T:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ConfigError("OpenAI package not installed: pip install ideagen[openai]")

        schema = json.dumps(response_type.model_json_schema(), indent=2)
        user_with_schema = (
            f"{user_prompt}\n\n"
            f"Respond with ONLY a valid JSON object matching this schema:\n"
            f"```json\n{schema}\n```\n"
            f"Do not include any text outside the JSON."
        )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_with_schema})

        client = AsyncOpenAI(api_key=self._api_key)
        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=messages,
                response_format={"type": "json_object"},
            )
            raw_text = response.choices[0].message.content or ""
        except Exception as e:
            raise ProviderError(f"OpenAI API error: {e}")

        try:
            raw_json = extract_json(raw_text)
        except ValueError as e:
            raise ProviderError(f"Failed to extract JSON from OpenAI response: {e}")

        return response_type.model_validate_json(raw_json)
