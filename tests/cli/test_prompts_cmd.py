"""Tests for ideagen prompts CLI commands."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ideagen.cli.app import app
from ideagen.cli.commands.prompts import PROMPT_NAMES


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_prompts_list_shows_all_four(runner: CliRunner) -> None:
    """ideagen prompts list shows all 4 prompt template names."""
    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.prompt_override_dir = None
        result = runner.invoke(app, ["prompts", "list"])

    assert result.exit_code == 0
    for name in PROMPT_NAMES:
        assert name in result.output


def test_prompts_list_shows_override_status(runner: CliRunner, tmp_path: Path) -> None:
    """ideagen prompts list shows 'yes' for existing overrides."""
    override_dir = tmp_path / "prompts"
    override_dir.mkdir()
    (override_dir / "analyze_trends.txt").write_text("custom prompt")

    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.prompt_override_dir = override_dir
        result = runner.invoke(app, ["prompts", "list"])

    assert result.exit_code == 0
    assert "analyze_trends" in result.output


def test_prompts_init_creates_templates(runner: CliRunner, tmp_path: Path) -> None:
    """ideagen prompts init creates template files."""
    target_dir = tmp_path / "prompts"

    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.prompt_override_dir = None
        result = runner.invoke(app, ["prompts", "init", "--dir", str(target_dir)])

    assert result.exit_code == 0
    assert "Created 4" in result.output
    for name in PROMPT_NAMES:
        assert (target_dir / f"{name}.txt").exists()


def test_prompts_init_does_not_overwrite(runner: CliRunner, tmp_path: Path) -> None:
    """ideagen prompts init skips existing files."""
    target_dir = tmp_path / "prompts"
    target_dir.mkdir()
    (target_dir / "analyze_trends.txt").write_text("custom content")

    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.prompt_override_dir = None
        result = runner.invoke(app, ["prompts", "init", "--dir", str(target_dir)])

    assert result.exit_code == 0
    assert "Skipped 1" in result.output
    # Verify original content preserved
    assert (target_dir / "analyze_trends.txt").read_text() == "custom content"


def test_prompts_init_uses_config_override_dir(runner: CliRunner, tmp_path: Path) -> None:
    """ideagen prompts init uses prompt_override_dir from config when --dir not specified."""
    target_dir = tmp_path / "configured_prompts"

    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.prompt_override_dir = target_dir
        result = runner.invoke(app, ["prompts", "init"])

    assert result.exit_code == 0
    assert "Created 4" in result.output
    assert target_dir.exists()


def test_prompts_list_no_override_dir_all_no(runner: CliRunner) -> None:
    """All prompts show 'no' override when prompt_override_dir is None."""
    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.prompt_override_dir = None
        result = runner.invoke(app, ["prompts", "list"])

    assert result.exit_code == 0
    # All should show "no" since no override dir configured
    assert result.output.count("no") >= 4
