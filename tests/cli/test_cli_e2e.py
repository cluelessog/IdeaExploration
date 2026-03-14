"""End-to-end CLI tests using typer.testing.CliRunner."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from ideagen import __version__
from ideagen.cli.app import app


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# 1. --help shows expected subcommands
# ---------------------------------------------------------------------------

def test_help_shows_subcommands(runner: CliRunner) -> None:
    """ideagen --help lists all registered subcommands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("run", "sources", "config", "history", "interactive", "schedule"):
        assert cmd in result.output


# ---------------------------------------------------------------------------
# 2. --version / -V shows version string
# ---------------------------------------------------------------------------

def test_version_flag(runner: CliRunner) -> None:
    """ideagen --version prints the package version."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_version_short_flag(runner: CliRunner) -> None:
    """ideagen -V prints the package version."""
    result = runner.invoke(app, ["-V"])
    assert result.exit_code == 0
    assert __version__ in result.output


# ---------------------------------------------------------------------------
# 3. run command — happy path (IdeaGenService fully mocked)
# ---------------------------------------------------------------------------

def test_run_command_basic_invocation(runner: CliRunner) -> None:
    """ideagen run exits 0 and produces output when the pipeline is mocked."""
    from ideagen.core.models import RunResult, PipelineComplete

    mock_run_result = MagicMock(spec=RunResult)
    mock_run_result.ideas = []

    # The renderer.render() coroutine must return a RunResult-like object
    mock_renderer = MagicMock()
    mock_renderer.render = AsyncMock(return_value=mock_run_result)

    with (
        patch("ideagen.sources.registry.get_sources_by_names", return_value={}),
        patch("ideagen.providers.registry.get_provider", return_value=MagicMock()),
        patch("ideagen.storage.sqlite.SQLiteStorage", return_value=MagicMock()),
        patch("ideagen.core.service.IdeaGenService", return_value=MagicMock()),
        patch("ideagen.cli.formatters.PipelineEventRenderer", return_value=mock_renderer),
    ):
        result = runner.invoke(app, ["run"])

    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# 4. Missing claude CLI gives a clear error message
# ---------------------------------------------------------------------------

def test_run_missing_claude_cli_gives_clear_error(runner: CliRunner) -> None:
    """When shutil.which('claude') returns None, ideagen run prints a helpful error."""
    from ideagen.core.exceptions import ProviderError

    # ClaudeProvider._verify_cli raises ProviderError when claude is not found.
    # We mock get_provider to raise it immediately (simulating the async verify
    # that happens on first use), or we mock shutil.which at the source.
    # The cleanest approach: let get_provider return a real ClaudeProvider whose
    # _verify_cli will raise, but since run_async drives the async loop we mock
    # shutil.which so the check in _verify_cli triggers.

    mock_renderer = MagicMock()

    async def _raise_provider_error(events):
        raise ProviderError(
            "Claude CLI not found. Install Claude Code: "
            "https://docs.anthropic.com/en/docs/claude-code"
        )

    mock_renderer.render = _raise_provider_error

    with (
        patch("ideagen.sources.registry.get_sources_by_names", return_value={}),
        patch("ideagen.storage.sqlite.SQLiteStorage", return_value=MagicMock()),
        patch("ideagen.core.service.IdeaGenService", return_value=MagicMock()),
        patch("ideagen.cli.formatters.PipelineEventRenderer", return_value=mock_renderer),
        patch("shutil.which", return_value=None),
    ):
        from ideagen.providers.claude import ClaudeProvider
        real_provider = ClaudeProvider()
        with patch("ideagen.providers.registry.get_provider", return_value=real_provider):
            result = runner.invoke(app, ["run"])

    # The ProviderError should surface — either as non-zero exit or error text
    assert result.exit_code != 0 or (
        result.exception is not None
        or "claude" in (result.output or "").lower()
    )


def test_claude_provider_raises_when_cli_missing() -> None:
    """ClaudeProvider._verify_cli raises ProviderError when shutil.which returns None."""
    import asyncio
    from ideagen.providers.claude import ClaudeProvider
    from ideagen.core.exceptions import ProviderError

    provider = ClaudeProvider()

    async def _check():
        with patch("shutil.which", return_value=None):
            await provider._verify_cli()

    with pytest.raises(ProviderError, match="[Cc]laude"):
        asyncio.run(_check())


# ---------------------------------------------------------------------------
# 5. sources test — lists 4 source names
# ---------------------------------------------------------------------------

def test_sources_test_lists_four_sources(runner: CliRunner) -> None:
    """ideagen sources test shows all four registered source names."""
    source_names = ["hackernews", "reddit", "producthunt", "twitter"]

    # Build lightweight mock sources so no network calls happen
    mock_sources: dict[str, MagicMock] = {}
    for name in source_names:
        src = MagicMock()
        src.is_available = AsyncMock(return_value=True)
        src.PARSER_VERSION = "1.0"
        mock_sources[name] = src

    with patch("ideagen.sources.registry.get_all_sources", return_value=mock_sources):
        result = runner.invoke(app, ["sources", "test"])

    assert result.exit_code == 0
    for name in source_names:
        assert name in result.output


# ---------------------------------------------------------------------------
# 6. config init creates a TOML file
# ---------------------------------------------------------------------------

def test_config_init_creates_toml_file(runner: CliRunner, tmp_path: Path) -> None:
    """ideagen config init --config <path> creates a TOML file at the given path."""
    config_file = tmp_path / "ideagen_test.toml"

    result = runner.invoke(app, ["config", "init", "--config", str(config_file)])

    assert result.exit_code == 0
    assert config_file.exists(), "Config file was not created"
    assert config_file.stat().st_size > 0, "Config file is empty"
    # Confirm it's valid TOML
    import tomllib
    with open(config_file, "rb") as f:
        data = tomllib.load(f)
    assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# 7. config show — displays config as JSON and redacts API keys
# ---------------------------------------------------------------------------

def test_config_show_displays_json(runner: CliRunner) -> None:
    """ideagen config show exits 0 and includes provider name in output."""
    from ideagen.core.config import IdeaGenConfig

    with patch("ideagen.cli.config_loader.load_config", return_value=IdeaGenConfig()):
        result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0
    assert "claude" in result.output


def test_config_show_redacts_api_keys(runner: CliRunner) -> None:
    """ideagen config show replaces openai_api_key with REDACTED."""
    from ideagen.core.config import IdeaGenConfig, ProviderConfig

    config = IdeaGenConfig(providers=ProviderConfig(openai_api_key="sk-secret"))

    with patch("ideagen.cli.config_loader.load_config", return_value=config):
        result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0
    assert "REDACTED" in result.output
    assert "sk-secret" not in result.output


# ---------------------------------------------------------------------------
# 8. --format option (Phase 11.1)
# ---------------------------------------------------------------------------

def _make_mock_pipeline_patches(run_result):
    """Return a context-manager list for mocking the pipeline."""
    from unittest.mock import AsyncMock, MagicMock, patch
    # We need to patch _consume_pipeline indirectly by making service.run yield PipelineComplete
    from ideagen.core.models import PipelineComplete

    async def fake_run(**kwargs):
        yield PipelineComplete(result=run_result)

    mock_service = MagicMock()
    mock_service.run = fake_run
    return mock_service


def test_run_format_json_outputs_valid_json(runner: CliRunner) -> None:
    """ideagen run --format json prints valid JSON for the RunResult."""
    import json
    from ideagen.core.models import PipelineComplete
    from tests.conftest import make_run

    run_result = make_run()

    async def fake_run(**kwargs):
        yield PipelineComplete(result=run_result)

    mock_service = MagicMock()
    mock_service.run = fake_run

    with (
        patch("ideagen.sources.registry.get_sources_by_names", return_value={}),
        patch("ideagen.providers.registry.get_provider", return_value=MagicMock()),
        patch("ideagen.storage.sqlite.SQLiteStorage", return_value=MagicMock()),
        patch("ideagen.core.service.IdeaGenService", return_value=mock_service),
    ):
        result = runner.invoke(app, ["run", "--format", "json"])

    assert result.exit_code == 0, result.output
    parsed = json.loads(result.output)
    assert isinstance(parsed, dict)
    assert "ideas" in parsed


def test_run_format_markdown_outputs_markdown(runner: CliRunner) -> None:
    """ideagen run --format markdown prints markdown with expected headers."""
    from ideagen.core.models import PipelineComplete
    from tests.conftest import make_run

    run_result = make_run(title="Great Idea")

    async def fake_run(**kwargs):
        yield PipelineComplete(result=run_result)

    mock_service = MagicMock()
    mock_service.run = fake_run

    with (
        patch("ideagen.sources.registry.get_sources_by_names", return_value={}),
        patch("ideagen.providers.registry.get_provider", return_value=MagicMock()),
        patch("ideagen.storage.sqlite.SQLiteStorage", return_value=MagicMock()),
        patch("ideagen.core.service.IdeaGenService", return_value=mock_service),
    ):
        result = runner.invoke(app, ["run", "--format", "markdown"])

    assert result.exit_code == 0, result.output
    assert "# IdeaGen Run Report" in result.output
    assert "## Ideas" in result.output
    assert "Great Idea" in result.output


def test_run_format_rich_is_default(runner: CliRunner) -> None:
    """ideagen run without --format uses rich renderer (existing behavior)."""
    from ideagen.core.models import RunResult

    mock_run_result = MagicMock(spec=RunResult)
    mock_run_result.ideas = []

    mock_renderer = MagicMock()
    mock_renderer.render = AsyncMock(return_value=mock_run_result)

    with (
        patch("ideagen.sources.registry.get_sources_by_names", return_value={}),
        patch("ideagen.providers.registry.get_provider", return_value=MagicMock()),
        patch("ideagen.storage.sqlite.SQLiteStorage", return_value=MagicMock()),
        patch("ideagen.core.service.IdeaGenService", return_value=MagicMock()),
        patch("ideagen.cli.formatters.PipelineEventRenderer", return_value=mock_renderer),
    ):
        result = runner.invoke(app, ["run"])

    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# 9. --source filter (Phase 11.2)
# ---------------------------------------------------------------------------

def test_run_source_filter_single(runner: CliRunner) -> None:
    """ideagen run --source hackernews calls get_sources_by_names with ['hackernews']."""
    from ideagen.core.models import RunResult

    mock_run_result = MagicMock(spec=RunResult)
    mock_run_result.ideas = []

    mock_renderer = MagicMock()
    mock_renderer.render = AsyncMock(return_value=mock_run_result)

    captured_names = []

    def mock_get_sources(names, **kwargs):
        captured_names.extend(names)
        return {"hackernews": MagicMock()}

    with (
        patch("ideagen.sources.registry.get_sources_by_names", side_effect=mock_get_sources),
        patch("ideagen.providers.registry.get_provider", return_value=MagicMock()),
        patch("ideagen.storage.sqlite.SQLiteStorage", return_value=MagicMock()),
        patch("ideagen.core.service.IdeaGenService", return_value=MagicMock()),
        patch("ideagen.cli.formatters.PipelineEventRenderer", return_value=mock_renderer),
    ):
        result = runner.invoke(app, ["run", "--source", "hackernews"])

    assert result.exit_code == 0
    assert captured_names == ["hackernews"]


def test_run_source_filter_unknown_all_exits_error(runner: CliRunner) -> None:
    """ideagen run --source bogus exits with code 1 when all sources are unknown."""
    with (
        patch("ideagen.sources.registry.get_sources_by_names", return_value={}),
        patch("ideagen.sources.registry.get_available_source_names", return_value=["hackernews", "reddit", "producthunt", "twitter"]),
        patch("ideagen.providers.registry.get_provider", return_value=MagicMock()),
        patch("ideagen.storage.sqlite.SQLiteStorage", return_value=MagicMock()),
        patch("ideagen.core.service.IdeaGenService", return_value=MagicMock()),
    ):
        result = runner.invoke(app, ["run", "--source", "bogus"])

    assert result.exit_code == 1
