"""Tests for ideagen run command input validation."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ideagen.cli.app import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_run_invalid_domain_rejected(runner: CliRunner) -> None:
    """Unknown domain value should error with a list of valid options."""
    result = runner.invoke(app, ["run", "--domain", "crypto", "--dry-run"])
    assert result.exit_code != 0
    output = result.output
    assert "crypto" in output
    # Should list valid options
    assert "software" in output
    assert "business" in output
    assert "content" in output


def test_run_valid_domains_accepted(runner: CliRunner) -> None:
    """Valid domain values should not produce an 'Unknown domain' validation error."""
    valid_domains = ["software", "business", "content"]

    # Patch load_config and run_async to prevent actual pipeline execution.
    # load_config is imported inside the function from ideagen.cli.config_loader.
    mock_config = MagicMock()
    mock_config.sources.enabled = []
    mock_config.providers = MagicMock()
    mock_config.storage.database_path = ":memory:"

    for domain in valid_domains:
        with patch("ideagen.cli.config_loader.load_config", return_value=mock_config), \
             patch("ideagen.cli.async_bridge.run_async", return_value=None), \
             patch("ideagen.sources.registry.get_sources_by_names", return_value=[MagicMock()]), \
             patch("ideagen.providers.registry.get_provider", return_value=MagicMock()), \
             patch("ideagen.storage.sqlite.SQLiteStorage", return_value=MagicMock()), \
             patch("ideagen.core.service.IdeaGenService", return_value=MagicMock()):
            result = runner.invoke(app, ["run", "--domain", domain, "--dry-run"])

        # Domain validation must not fire for valid domains.
        assert "Unknown domain" not in result.output, (
            f"Domain '{domain}' should be valid but got validation error: {result.output}"
        )
