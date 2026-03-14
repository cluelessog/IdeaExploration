"""Tests for provider registry get_provider()."""
from __future__ import annotations
import sys
from unittest.mock import MagicMock, patch

import pytest

from ideagen.core.config import ProviderConfig
from ideagen.core.exceptions import ConfigError
from ideagen.providers.claude import ClaudeProvider
from ideagen.providers.registry import get_provider


def test_get_provider_returns_claude_by_default():
    config = ProviderConfig(default="claude")
    provider = get_provider(config)
    assert isinstance(provider, ClaudeProvider)


def test_get_provider_openai_import_error():
    config = ProviderConfig(default="openai", openai_api_key="sk-test")
    with patch.dict("sys.modules", {"ideagen.providers.openai_provider": None}):
        with pytest.raises(ConfigError, match="pip install ideagen\\[openai\\]"):
            get_provider(config)


def test_get_provider_openai_missing_api_key():
    mock_module = MagicMock()
    mock_module.OpenAIProvider = MagicMock()
    config = ProviderConfig(default="openai", openai_api_key=None)
    with patch.dict("sys.modules", {"ideagen.providers.openai_provider": mock_module}):
        with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
            get_provider(config)


def test_get_provider_openai_success():
    mock_instance = MagicMock()
    mock_class = MagicMock(return_value=mock_instance)
    mock_module = MagicMock()
    mock_module.OpenAIProvider = mock_class
    config = ProviderConfig(default="openai", openai_api_key="sk-test", model="gpt-4")
    with patch.dict("sys.modules", {"ideagen.providers.openai_provider": mock_module}):
        result = get_provider(config)
    mock_class.assert_called_once_with(api_key="sk-test", model="gpt-4")
    assert result is mock_instance


def test_get_provider_gemini_import_error():
    config = ProviderConfig(default="gemini", gemini_api_key="AIza-test")
    with patch.dict("sys.modules", {"ideagen.providers.gemini": None}):
        with pytest.raises(ConfigError, match="pip install ideagen\\[gemini\\]"):
            get_provider(config)


def test_get_provider_gemini_missing_api_key():
    mock_module = MagicMock()
    mock_module.GeminiProvider = MagicMock()
    config = ProviderConfig(default="gemini", gemini_api_key=None)
    with patch.dict("sys.modules", {"ideagen.providers.gemini": mock_module}):
        with pytest.raises(ConfigError, match="GEMINI_API_KEY"):
            get_provider(config)


def test_get_provider_gemini_success():
    mock_instance = MagicMock()
    mock_class = MagicMock(return_value=mock_instance)
    mock_module = MagicMock()
    mock_module.GeminiProvider = mock_class
    config = ProviderConfig(default="gemini", gemini_api_key="AIza-test", model="gemini-pro")
    with patch.dict("sys.modules", {"ideagen.providers.gemini": mock_module}):
        result = get_provider(config)
    mock_class.assert_called_once_with(api_key="AIza-test", model="gemini-pro")
    assert result is mock_instance


def test_get_provider_unknown_name():
    config = ProviderConfig(default="llama")
    with pytest.raises(ConfigError, match="Unknown provider"):
        get_provider(config)
