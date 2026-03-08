"""Tests for Gemini provider (mocked SDK)."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from ideagen.core.exceptions import ConfigError, ProviderError


class SampleResponse(BaseModel):
    answer: str
    score: int


class TestGeminiProviderImportGuard:
    def test_init_succeeds_when_genai_available(self):
        mock_google = MagicMock()
        mock_genai = MagicMock()
        with patch.dict(sys.modules, {"google": mock_google, "google.genai": mock_genai}):
            from ideagen.providers.gemini import GeminiProvider
            provider = GeminiProvider(api_key="test-key")
            assert provider._model == "gemini-2.0-flash"

    def test_custom_model(self):
        mock_google = MagicMock()
        mock_genai = MagicMock()
        with patch.dict(sys.modules, {"google": mock_google, "google.genai": mock_genai}):
            from ideagen.providers.gemini import GeminiProvider
            provider = GeminiProvider(api_key="test-key", model="gemini-2.5-pro")
            assert provider._model == "gemini-2.5-pro"


class TestGeminiProviderComplete:
    @pytest.mark.asyncio
    async def test_returns_validated_model(self):
        mock_google = MagicMock()
        mock_genai = MagicMock()
        response_json = json.dumps({"answer": "gemini answer", "score": 99})

        mock_aio = AsyncMock()
        mock_aio.models.generate_content = AsyncMock(
            return_value=SimpleNamespace(text=response_json)
        )
        mock_client = MagicMock()
        mock_client.aio = mock_aio
        mock_genai.Client = MagicMock(return_value=mock_client)

        with patch.dict(sys.modules, {"google": mock_google, "google.genai": mock_genai}):
            # Patch genai in the provider module's namespace
            with patch("ideagen.providers.gemini.genai", mock_genai, create=True):
                from ideagen.providers.gemini import GeminiProvider
                provider = GeminiProvider.__new__(GeminiProvider)
                provider._api_key = "test-key"
                provider._model = "gemini-2.0-flash"

                # Patch the import inside complete()
                with patch.dict(sys.modules, {"google": mock_google, "google.genai": mock_genai}):
                    mock_google.genai = mock_genai
                    result = await provider.complete("test prompt", SampleResponse)

        assert isinstance(result, SampleResponse)
        assert result.answer == "gemini answer"
        assert result.score == 99

    @pytest.mark.asyncio
    async def test_handles_api_error(self):
        mock_google = MagicMock()
        mock_genai = MagicMock()

        mock_aio = AsyncMock()
        mock_aio.models.generate_content = AsyncMock(
            side_effect=Exception("Quota exceeded")
        )
        mock_client = MagicMock()
        mock_client.aio = mock_aio
        mock_genai.Client = MagicMock(return_value=mock_client)

        with patch.dict(sys.modules, {"google": mock_google, "google.genai": mock_genai}):
            mock_google.genai = mock_genai
            from ideagen.providers.gemini import GeminiProvider
            provider = GeminiProvider.__new__(GeminiProvider)
            provider._api_key = "test-key"
            provider._model = "gemini-2.0-flash"
            with pytest.raises(ProviderError, match="Gemini API error"):
                await provider.complete("test", SampleResponse)

    @pytest.mark.asyncio
    async def test_passes_system_prompt_in_content(self):
        mock_google = MagicMock()
        mock_genai = MagicMock()
        response_json = json.dumps({"answer": "ok", "score": 1})

        mock_aio = AsyncMock()
        mock_aio.models.generate_content = AsyncMock(
            return_value=SimpleNamespace(text=response_json)
        )
        mock_client = MagicMock()
        mock_client.aio = mock_aio
        mock_genai.Client = MagicMock(return_value=mock_client)

        with patch.dict(sys.modules, {"google": mock_google, "google.genai": mock_genai}):
            mock_google.genai = mock_genai
            from ideagen.providers.gemini import GeminiProvider
            provider = GeminiProvider.__new__(GeminiProvider)
            provider._api_key = "test-key"
            provider._model = "gemini-2.0-flash"
            await provider.complete("test", SampleResponse, system_prompt="Be creative")

        call_args = mock_aio.models.generate_content.call_args
        contents = call_args.kwargs.get("contents", call_args[1].get("contents", ""))
        assert "Be creative" in contents
