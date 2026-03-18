"""Tests for the 'ask' CLI command."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from ideagen.cli.app import app
from ideagen.core.nl_interpreter import NLAction


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _make_action(command: str = "sources_list", args: dict | None = None,
                 explanation: str = "List sources", confidence: float = 0.9) -> NLAction:
    return NLAction(command=command, args=args or {}, explanation=explanation, confidence=confidence)


# ---------------------------------------------------------------------------
# Basic command routing tests
# ---------------------------------------------------------------------------


def test_ask_sources_list(runner: CliRunner) -> None:
    """'ask' with a sources query calls NLInterpreter and executes sources_list."""
    action = _make_action("sources_list", explanation="List available data sources")

    mock_instance = MagicMock()
    mock_instance.interpret = AsyncMock(return_value=action)

    with (
        patch("ideagen.core.nl_interpreter.NLInterpreter", return_value=mock_instance),
        patch("ideagen.cli.commands.ask._execute_action") as mock_exec,
    ):
        result = runner.invoke(app, ["ask", "what sources are available?"])

    assert result.exit_code == 0
    assert "Interpreted" in result.output
    assert "List available data sources" in result.output
    mock_exec.assert_called_once_with(action)


def test_ask_config_show(runner: CliRunner) -> None:
    action = _make_action("config_show", explanation="Show current configuration")

    mock_instance = MagicMock()
    mock_instance.interpret = AsyncMock(return_value=action)

    with (
        patch("ideagen.core.nl_interpreter.NLInterpreter", return_value=mock_instance),
        patch("ideagen.cli.commands.ask._execute_action") as mock_exec,
    ):
        result = runner.invoke(app, ["ask", "show my config"])

    assert result.exit_code == 0
    assert "Show current configuration" in result.output
    mock_exec.assert_called_once_with(action)


def test_ask_run_command(runner: CliRunner) -> None:
    action = _make_action(
        "run",
        args={"domain": "software", "source": ["hackernews"]},
        explanation="Run idea generation for software from HackerNews",
        confidence=0.95,
    )

    mock_instance = MagicMock()
    mock_instance.interpret = AsyncMock(return_value=action)

    with (
        patch("ideagen.core.nl_interpreter.NLInterpreter", return_value=mock_instance),
        patch("ideagen.cli.commands.ask._execute_action") as mock_exec,
    ):
        result = runner.invoke(app, ["ask", "find software ideas from hackernews"])

    assert result.exit_code == 0
    assert "95%" in result.output  # confidence display
    mock_exec.assert_called_once_with(action)


# ---------------------------------------------------------------------------
# Confidence threshold tests
# ---------------------------------------------------------------------------


def test_ask_low_confidence_prompts_confirm(runner: CliRunner) -> None:
    """Low confidence (<0.7) should ask for confirmation."""
    action = _make_action("run", confidence=0.5, explanation="Uncertain interpretation")

    mock_instance = MagicMock()
    mock_instance.interpret = AsyncMock(return_value=action)

    with (
        patch("ideagen.core.nl_interpreter.NLInterpreter", return_value=mock_instance),
        patch("ideagen.cli.commands.ask._execute_action") as mock_exec,
    ):
        # User declines confirmation
        result = runner.invoke(app, ["ask", "something vague"], input="n\n")

    assert result.exit_code == 0
    assert "Cancelled" in result.output
    mock_exec.assert_not_called()


def test_ask_low_confidence_proceed_with_yes_flag(runner: CliRunner) -> None:
    """--yes flag skips confirmation even with low confidence."""
    action = _make_action("run", confidence=0.5, explanation="Uncertain interpretation")

    mock_instance = MagicMock()
    mock_instance.interpret = AsyncMock(return_value=action)

    with (
        patch("ideagen.core.nl_interpreter.NLInterpreter", return_value=mock_instance),
        patch("ideagen.cli.commands.ask._execute_action") as mock_exec,
    ):
        result = runner.invoke(app, ["ask", "--yes", "something vague"])

    assert result.exit_code == 0
    mock_exec.assert_called_once_with(action)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_ask_interpreter_returns_none(runner: CliRunner) -> None:
    """If interpret returns None, exit with error."""
    mock_instance = MagicMock()
    mock_instance.interpret = AsyncMock(return_value=None)

    with (
        patch("ideagen.core.nl_interpreter.NLInterpreter", return_value=mock_instance),
        patch("ideagen.cli.async_bridge.run_async", return_value=None),
    ):
        result = runner.invoke(app, ["ask", "gibberish"])

    assert result.exit_code == 1
    assert "Failed to interpret" in result.output


def test_ask_unknown_command(runner: CliRunner) -> None:
    """Unknown command from interpreter shows error."""
    action = _make_action("nonexistent_command", explanation="Bad command")

    mock_instance = MagicMock()
    mock_instance.interpret = AsyncMock(return_value=action)

    with patch("ideagen.core.nl_interpreter.NLInterpreter", return_value=mock_instance):
        result = runner.invoke(app, ["ask", "do something weird"])

    assert result.exit_code == 1
    assert "Unknown command" in result.output


# ---------------------------------------------------------------------------
# _execute_action routing tests
# ---------------------------------------------------------------------------


def test_execute_action_routes_sources_list() -> None:
    """_execute_action routes sources_list to the right handler."""
    from ideagen.cli.commands.ask import _execute_action

    action = _make_action("sources_list")

    with patch("ideagen.cli.commands.ask._execute_sources_list") as mock_fn:
        _execute_action(action)
        mock_fn.assert_called_once()


def test_execute_action_routes_config_show() -> None:
    from ideagen.cli.commands.ask import _execute_action

    action = _make_action("config_show")

    with patch("ideagen.cli.commands.ask._execute_config_show") as mock_fn:
        _execute_action(action)
        mock_fn.assert_called_once()


def test_execute_action_routes_history_list() -> None:
    from ideagen.cli.commands.ask import _execute_action

    action = _make_action("history_list")

    with patch("ideagen.cli.commands.ask._execute_history_list") as mock_fn:
        _execute_action(action)
        mock_fn.assert_called_once()


def test_execute_action_routes_run() -> None:
    from ideagen.cli.commands.ask import _execute_action

    action = _make_action("run", args={"domain": "software"})

    with patch("ideagen.cli.commands.ask._execute_run") as mock_fn:
        _execute_action(action)
        mock_fn.assert_called_once_with({"domain": "software"})


def test_execute_action_routes_compare() -> None:
    from ideagen.cli.commands.ask import _execute_action

    action = _make_action("compare", args={"run1": "abc", "run2": "def"})

    with patch("ideagen.cli.commands.ask._execute_compare") as mock_fn:
        _execute_action(action)
        mock_fn.assert_called_once_with({"run1": "abc", "run2": "def"})
