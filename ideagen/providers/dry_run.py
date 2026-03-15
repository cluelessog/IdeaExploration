"""No-op AI provider used during --dry-run mode."""
from __future__ import annotations

from ideagen.providers.base import AIProvider
from ideagen.core.exceptions import ProviderError


class DryRunProvider(AIProvider):
    """No-op provider used during --dry-run. Raises if complete() is ever called."""

    async def complete(self, user_prompt, response_type, system_prompt=None):
        raise ProviderError(
            "DryRunProvider should never be called — dry-run mode does not use AI"
        )
