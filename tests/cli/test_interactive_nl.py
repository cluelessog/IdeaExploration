"""Tests for the interactive REPL NL interpretation fallback."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from ideagen.cli.app import app
from ideagen.core.nl_interpreter import NLAction


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_repl_deps():
    with (
        patch("ideagen.cli.config_loader.load_config") as mock_config,
        patch("ideagen.sources.registry.get_sources_by_names", return_value={}),
        patch("ideagen.providers.registry.get_provider", return_value=MagicMock()),
        patch("ideagen.core.service.IdeaGenService") as mock_svc,
        patch("ideagen.cli.commands.interactive.Prompt") as mock_prompt,
    ):
        from ideagen.core.config import IdeaGenConfig

        mock_config.return_value = IdeaGenConfig()
        yield {"config": mock_config, "service": mock_svc, "prompt": mock_prompt}


def test_interactive_unknown_cmd_tries_nl(runner: CliRunner, mock_repl_deps: dict) -> None:
    """Unrecognized commands in the REPL are passed to _try_nl_interpret."""
    mock_repl_deps["prompt"].ask.side_effect = ["what sources exist?", "quit"]

    action = NLAction(
        command="sources_list",
        args={},
        explanation="List available data sources",
        confidence=0.9,
    )

    mock_instance = MagicMock()
    mock_instance.interpret = AsyncMock(return_value=action)

    with (
        patch("ideagen.core.nl_interpreter.NLInterpreter", return_value=mock_instance),
        patch("ideagen.cli.commands.ask._execute_action") as mock_exec,
    ):
        result = runner.invoke(app, ["interactive"])

    assert result.exit_code == 0
    assert "Interpreted" in result.output
    mock_exec.assert_called_once_with(action)


def test_interactive_nl_provider_error_shows_help(runner: CliRunner, mock_repl_deps: dict) -> None:
    """If Claude CLI is unavailable, show help + tip instead of crashing."""
    from ideagen.core.exceptions import ProviderError

    mock_repl_deps["prompt"].ask.side_effect = ["something natural", "quit"]

    mock_instance = MagicMock()
    mock_instance.interpret = AsyncMock(side_effect=ProviderError("Claude CLI not found"))

    with patch("ideagen.core.nl_interpreter.NLInterpreter", return_value=mock_instance):
        result = runner.invoke(app, ["interactive"])

    assert result.exit_code == 0
    assert "generate" in result.output  # Help commands shown
    assert "natural language" in result.output  # Tip about Claude CLI


def test_interactive_nl_low_confidence_asks_confirm(runner: CliRunner, mock_repl_deps: dict) -> None:
    """Low confidence NL interpretation in REPL asks for confirmation."""
    mock_repl_deps["prompt"].ask.side_effect = ["do something", "quit"]

    action = NLAction(
        command="run",
        args={},
        explanation="Uncertain interpretation",
        confidence=0.4,
    )

    mock_instance = MagicMock()
    mock_instance.interpret = AsyncMock(return_value=action)

    with (
        patch("ideagen.core.nl_interpreter.NLInterpreter", return_value=mock_instance),
        patch("rich.prompt.Confirm") as mock_confirm,
        patch("ideagen.cli.commands.ask._execute_action") as mock_exec,
    ):
        mock_confirm.ask.return_value = False  # User declines

        result = runner.invoke(app, ["interactive"])

    assert result.exit_code == 0
    assert "Cancelled" in result.output
    mock_exec.assert_not_called()


def test_interactive_known_cmds_still_work(runner: CliRunner, mock_repl_deps: dict) -> None:
    """Known commands (quit, list, etc.) are NOT passed to NL interpreter."""
    mock_repl_deps["prompt"].ask.side_effect = ["list", "quit"]

    with patch("ideagen.cli.commands.interactive._try_nl_interpret") as mock_nl:
        result = runner.invoke(app, ["interactive"])

    assert result.exit_code == 0
    # 'list' is a known command, should not trigger NL
    mock_nl.assert_not_called()
    assert "No ideas yet" in result.output
