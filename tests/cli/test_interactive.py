"""Tests for the interactive REPL command."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from ideagen.cli.app import app
from tests.conftest import make_report, make_run


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


def _setup_generate(mock_repl_deps: dict) -> MagicMock:
    """Patch PipelineEventRenderer so generate works; returns the mock renderer instance."""
    run_result = make_run()
    mock_renderer_instance = MagicMock()
    mock_renderer_instance.render = AsyncMock(return_value=run_result)

    mock_renderer_cls = MagicMock(return_value=mock_renderer_instance)

    # Also patch format_run_summary so it returns something printable
    with patch("ideagen.cli.formatters.PipelineEventRenderer", mock_renderer_cls):
        pass  # just to verify path; callers must apply context themselves

    return mock_renderer_cls, mock_renderer_instance, run_result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_interactive_quit_exits_cleanly(runner: CliRunner, mock_repl_deps: dict) -> None:
    """Prompt returns 'quit'; exit code 0, 'Goodbye' and banner in output."""
    mock_repl_deps["prompt"].ask.side_effect = ["quit"]
    result = runner.invoke(app, ["interactive"])
    assert result.exit_code == 0
    assert "Goodbye" in result.output
    # CANARY
    assert "Interactive Mode" in result.output


def test_interactive_exit_command(runner: CliRunner, mock_repl_deps: dict) -> None:
    """Prompt returns 'exit'; 'Goodbye' appears in output."""
    mock_repl_deps["prompt"].ask.side_effect = ["exit"]
    result = runner.invoke(app, ["interactive"])
    assert result.exit_code == 0
    assert "Goodbye" in result.output


def test_interactive_shows_welcome_banner(runner: CliRunner, mock_repl_deps: dict) -> None:
    """Welcome banner and command list shown on startup."""
    mock_repl_deps["prompt"].ask.side_effect = ["quit"]
    result = runner.invoke(app, ["interactive"])
    assert "Interactive Mode" in result.output
    assert "Commands:" in result.output


def test_interactive_unknown_command_shows_help(runner: CliRunner, mock_repl_deps: dict) -> None:
    """Unknown command triggers NL interpretation; on failure shows help."""
    from ideagen.core.exceptions import ProviderError

    mock_repl_deps["prompt"].ask.side_effect = ["foobar", "quit"]

    mock_instance = MagicMock()
    mock_instance.interpret = AsyncMock(side_effect=ProviderError("not available"))

    with patch("ideagen.core.nl_interpreter.NLInterpreter", return_value=mock_instance):
        result = runner.invoke(app, ["interactive"])

    assert result.exit_code == 0
    assert "generate" in result.output


def test_interactive_generate_triggers_pipeline(runner: CliRunner, mock_repl_deps: dict) -> None:
    """'generate' causes IdeaGenService to be instantiated and the pipeline to run."""
    run_result = make_run()
    mock_renderer_instance = MagicMock()
    mock_renderer_instance.render = AsyncMock(return_value=run_result)
    mock_renderer_cls = MagicMock(return_value=mock_renderer_instance)

    mock_repl_deps["prompt"].ask.side_effect = ["generate", "quit"]

    with patch("ideagen.cli.formatters.PipelineEventRenderer", mock_renderer_cls):
        result = runner.invoke(app, ["interactive"])

    assert result.exit_code == 0
    mock_repl_deps["service"].assert_called_once()


def test_interactive_list_without_generate_warns(runner: CliRunner, mock_repl_deps: dict) -> None:
    """'list' before 'generate' prints a warning."""
    mock_repl_deps["prompt"].ask.side_effect = ["list", "quit"]
    result = runner.invoke(app, ["interactive"])
    assert result.exit_code == 0
    assert "No ideas yet" in result.output


def test_interactive_list_shows_ideas_after_generate(runner: CliRunner, mock_repl_deps: dict) -> None:
    """'list' after 'generate' shows idea titles in a table."""
    run_result = make_run("My Test Idea")
    mock_renderer_instance = MagicMock()
    mock_renderer_instance.render = AsyncMock(return_value=run_result)
    mock_renderer_cls = MagicMock(return_value=mock_renderer_instance)

    mock_repl_deps["prompt"].ask.side_effect = ["generate", "list", "quit"]

    with patch("ideagen.cli.formatters.PipelineEventRenderer", mock_renderer_cls):
        result = runner.invoke(app, ["interactive"])

    assert result.exit_code == 0
    assert "My Test Idea" in result.output


def test_interactive_detail_shows_idea_card(runner: CliRunner, mock_repl_deps: dict) -> None:
    """'detail 1' after 'generate' calls format_idea_card and prints the result."""
    run_result = make_run("Detail Idea")
    mock_renderer_instance = MagicMock()
    mock_renderer_instance.render = AsyncMock(return_value=run_result)
    mock_renderer_cls = MagicMock(return_value=mock_renderer_instance)

    mock_repl_deps["prompt"].ask.side_effect = ["generate", "detail 1", "quit"]

    sentinel = "DETAIL_CARD_OUTPUT"

    with (
        patch("ideagen.cli.formatters.PipelineEventRenderer", mock_renderer_cls),
        patch("ideagen.cli.formatters.format_idea_card", return_value=sentinel) as mock_card,
    ):
        result = runner.invoke(app, ["interactive"])

    assert result.exit_code == 0
    mock_card.assert_called_once_with(run_result.ideas[0])
    assert sentinel in result.output


def test_interactive_detail_invalid_index(runner: CliRunner, mock_repl_deps: dict) -> None:
    """'detail 99' with only one idea shows usage error."""
    run_result = make_run()
    mock_renderer_instance = MagicMock()
    mock_renderer_instance.render = AsyncMock(return_value=run_result)
    mock_renderer_cls = MagicMock(return_value=mock_renderer_instance)

    mock_repl_deps["prompt"].ask.side_effect = ["generate", "detail 99", "quit"]

    with patch("ideagen.cli.formatters.PipelineEventRenderer", mock_renderer_cls):
        result = runner.invoke(app, ["interactive"])

    assert result.exit_code == 0
    assert "Usage: detail" in result.output


def test_interactive_detail_without_generate_warns(runner: CliRunner, mock_repl_deps: dict) -> None:
    """'detail 1' before 'generate' prints a warning."""
    mock_repl_deps["prompt"].ask.side_effect = ["detail 1", "quit"]
    result = runner.invoke(app, ["interactive"])
    assert result.exit_code == 0
    assert "No ideas yet" in result.output


def test_interactive_export_calls_json_export(runner: CliRunner, mock_repl_deps: dict) -> None:
    """'export' after 'generate' calls export_run and reports the path."""
    run_result = make_run()
    mock_renderer_instance = MagicMock()
    mock_renderer_instance.render = AsyncMock(return_value=run_result)
    mock_renderer_cls = MagicMock(return_value=mock_renderer_instance)

    mock_repl_deps["prompt"].ask.side_effect = ["generate", "export", "quit"]

    with (
        patch("ideagen.cli.formatters.PipelineEventRenderer", mock_renderer_cls),
        patch("ideagen.storage.json_export.export_run", return_value=Path("/tmp/out.json")) as mock_export,
    ):
        result = runner.invoke(app, ["interactive"])

    assert result.exit_code == 0
    mock_export.assert_called_once_with(run_result)
    assert "Exported" in result.output


def test_interactive_export_without_generate_warns(runner: CliRunner, mock_repl_deps: dict) -> None:
    """'export' before 'generate' prints a warning."""
    mock_repl_deps["prompt"].ask.side_effect = ["export", "quit"]
    result = runner.invoke(app, ["interactive"])
    assert result.exit_code == 0
    assert "No results to export" in result.output


def test_interactive_eof_exits_gracefully(runner: CliRunner, mock_repl_deps: dict) -> None:
    """EOFError from Prompt.ask exits cleanly with exit code 0."""
    mock_repl_deps["prompt"].ask.side_effect = EOFError
    result = runner.invoke(app, ["interactive"])
    assert result.exit_code == 0
    assert "Goodbye" in result.output


def test_interactive_keyboard_interrupt_exits(runner: CliRunner, mock_repl_deps: dict) -> None:
    """KeyboardInterrupt from Prompt.ask exits cleanly with exit code 0."""
    mock_repl_deps["prompt"].ask.side_effect = KeyboardInterrupt
    result = runner.invoke(app, ["interactive"])
    assert result.exit_code == 0
    assert "Goodbye" in result.output
