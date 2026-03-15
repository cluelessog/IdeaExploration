"""Tests for DryRunProvider and dry-run CLI behavior."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from typer.testing import CliRunner

from ideagen.core.exceptions import ProviderError


# ---------------------------------------------------------------------------
# 1. DryRunProvider.complete() raises ProviderError
# ---------------------------------------------------------------------------

def test_dry_run_provider_raises_on_complete():
    """DryRunProvider.complete() must raise ProviderError — it should never be called."""
    import asyncio
    from ideagen.providers.dry_run import DryRunProvider

    provider = DryRunProvider()

    async def _call():
        from pydantic import BaseModel

        class FakeModel(BaseModel):
            value: str

        await provider.complete("some prompt", FakeModel)

    with pytest.raises(ProviderError, match="dry-run"):
        asyncio.run(_call())


# ---------------------------------------------------------------------------
# 2. CLI dry-run with missing API key succeeds (get_provider not called)
# ---------------------------------------------------------------------------

def test_dry_run_no_provider_needed():
    """ideagen run --dry-run must succeed even if get_provider would raise."""
    from ideagen.core.exceptions import ConfigError
    from ideagen.core.models import RunResult
    from ideagen.cli.app import app

    runner = CliRunner()

    mock_run_result = MagicMock(spec=RunResult)
    mock_run_result.ideas = []

    mock_renderer = MagicMock()
    mock_renderer.render = AsyncMock(return_value=mock_run_result)

    def _raise_config_error(*args, **kwargs):
        raise ConfigError("OpenAI provider requires OPENAI_API_KEY environment variable")

    with (
        patch("ideagen.sources.registry.get_sources_by_names", return_value={}),
        patch("ideagen.providers.registry.get_provider", side_effect=_raise_config_error),
        patch("ideagen.storage.sqlite.SQLiteStorage", return_value=MagicMock()),
        patch("ideagen.core.service.IdeaGenService", return_value=MagicMock()),
        patch("ideagen.cli.formatters.PipelineEventRenderer", return_value=mock_renderer),
    ):
        result = runner.invoke(app, ["run", "--dry-run"])

    assert result.exit_code == 0, f"Expected exit 0 but got {result.exit_code}. Output: {result.output}"


# ---------------------------------------------------------------------------
# 3. Normal (non-dry-run) run still calls get_provider
# ---------------------------------------------------------------------------

def test_non_dry_run_still_validates_provider():
    """ideagen run (without --dry-run) must call get_provider normally."""
    from ideagen.core.models import RunResult
    from ideagen.cli.app import app

    runner = CliRunner()

    mock_run_result = MagicMock(spec=RunResult)
    mock_run_result.ideas = []

    mock_renderer = MagicMock()
    mock_renderer.render = AsyncMock(return_value=mock_run_result)

    get_provider_called = []

    def _track_get_provider(*args, **kwargs):
        get_provider_called.append(True)
        return MagicMock()

    with (
        patch("ideagen.sources.registry.get_sources_by_names", return_value={}),
        patch("ideagen.providers.registry.get_provider", side_effect=_track_get_provider),
        patch("ideagen.storage.sqlite.SQLiteStorage", return_value=MagicMock()),
        patch("ideagen.core.service.IdeaGenService", return_value=MagicMock()),
        patch("ideagen.cli.formatters.PipelineEventRenderer", return_value=mock_renderer),
    ):
        result = runner.invoke(app, ["run"])

    assert result.exit_code == 0
    assert get_provider_called, "get_provider should have been called for a normal (non-dry-run) invocation"
