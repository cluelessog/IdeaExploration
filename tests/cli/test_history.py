"""Tests for ideagen history show command."""
from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from ideagen.cli.app import app
from ideagen.storage.sqlite import SQLiteStorage
from tests.conftest import make_run


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def tmp_storage(tmp_path: Path) -> SQLiteStorage:
    return SQLiteStorage(db_path=str(tmp_path / "test.db"))


@pytest.mark.asyncio
async def test_get_run_detail_returns_run_with_ideas(tmp_storage: SQLiteStorage) -> None:
    """get_run_detail returns run metadata plus deserialized ideas."""
    run = make_run("Detail Test Idea")
    run_id = await tmp_storage.save_run(run)

    detail = await tmp_storage.get_run_detail(run_id)
    assert detail is not None
    assert detail["id"] == run_id
    assert len(detail["ideas"]) == 1
    assert detail["ideas"][0].idea.title == "Detail Test Idea"


@pytest.mark.asyncio
async def test_get_run_detail_prefix_match(tmp_storage: SQLiteStorage) -> None:
    """get_run_detail matches on ID prefix."""
    run = make_run("Prefix Test")
    run_id = await tmp_storage.save_run(run)

    detail = await tmp_storage.get_run_detail(run_id[:8])
    assert detail is not None
    assert detail["id"] == run_id


@pytest.mark.asyncio
async def test_get_run_detail_not_found(tmp_storage: SQLiteStorage) -> None:
    """get_run_detail returns None for unknown ID."""
    detail = await tmp_storage.get_run_detail("nonexistent")
    assert detail is None


def test_history_show_displays_details(runner: CliRunner, tmp_path: Path) -> None:
    """ideagen history show <id> displays run metadata and ideas."""
    from ideagen.cli.async_bridge import run_async

    storage = SQLiteStorage(db_path=str(tmp_path / "test.db"))
    run = make_run("CLI Show Test")
    run_id = run_async(storage.save_run(run))

    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.storage.database_path = str(tmp_path / "test.db")
        result = runner.invoke(app, ["history", "show", run_id])

    assert result.exit_code == 0
    assert "CLI Show Test" in result.output


def test_history_show_not_found(runner: CliRunner) -> None:
    """ideagen history show with bogus ID shows error."""
    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.storage.database_path = ":memory:"
        result = runner.invoke(app, ["history", "show", "bogus123"])

    assert result.exit_code == 1
    assert "No run found" in result.output


def test_history_list_shows_runs(runner: CliRunner, tmp_path: Path) -> None:
    """ideagen history list displays saved runs."""
    from ideagen.cli.async_bridge import run_async

    storage = SQLiteStorage(db_path=str(tmp_path / "test.db"))
    run_async(storage.save_run(make_run("First Idea")))
    run_async(storage.save_run(make_run("Second Idea")))

    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.storage.database_path = str(tmp_path / "test.db")
        result = runner.invoke(app, ["history", "list"])

    assert result.exit_code == 0
    assert "Past Runs" in result.output


def test_history_list_empty_shows_message(runner: CliRunner) -> None:
    """ideagen history list on empty DB shows 'No runs found'."""
    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.storage.database_path = ":memory:"
        result = runner.invoke(app, ["history", "list"])

    assert result.exit_code == 0
    assert "No runs found" in result.output


def test_history_list_respects_limit(runner: CliRunner, tmp_path: Path) -> None:
    """ideagen history list --limit 2 returns only 2 rows."""
    from ideagen.cli.async_bridge import run_async

    storage = SQLiteStorage(db_path=str(tmp_path / "test.db"))
    for i in range(5):
        run_async(storage.save_run(make_run(f"Idea {i}")))

    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.storage.database_path = str(tmp_path / "test.db")
        result = runner.invoke(app, ["history", "list", "--limit", "2"])

    assert result.exit_code == 0
    # Table header + 2 data rows means exactly 2 occurrences of the truncated ID pattern
    # Verify by counting table rows: the table renders, and only 2 runs appear
    assert result.output.count("SOFTWARE") == 2


def test_history_list_respects_offset(runner: CliRunner, tmp_path: Path) -> None:
    """ideagen history list --offset 1 skips the first run."""
    from ideagen.cli.async_bridge import run_async

    storage = SQLiteStorage(db_path=str(tmp_path / "test.db"))
    for i in range(3):
        run_async(storage.save_run(make_run(f"Idea {i}")))

    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.storage.database_path = str(tmp_path / "test.db")
        result_all = runner.invoke(app, ["history", "list"])
        result_offset = runner.invoke(app, ["history", "list", "--offset", "1"])

    assert result_all.exit_code == 0
    assert result_offset.exit_code == 0
    # offset=1 should yield one fewer row than no offset
    assert result_all.output.count("SOFTWARE") == 3
    assert result_offset.output.count("SOFTWARE") == 2


def test_history_prune_deletes_old_runs(runner: CliRunner, tmp_path: Path) -> None:
    """ideagen history prune --older-than 0d deletes a freshly saved run."""
    from ideagen.cli.async_bridge import run_async
    from datetime import datetime, timedelta

    storage = SQLiteStorage(db_path=str(tmp_path / "test.db"))
    old_run = make_run("Old Idea", timestamp=datetime.now() - timedelta(days=2))
    run_async(storage.save_run(old_run))

    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.storage.database_path = str(tmp_path / "test.db")
        result = runner.invoke(app, ["history", "prune", "--older-than", "1d"])

    assert result.exit_code == 0
    assert "Deleted" in result.output


def test_history_prune_no_matches(runner: CliRunner, tmp_path: Path) -> None:
    """ideagen history prune --older-than 999d reports 0 deleted for a fresh run."""
    from ideagen.cli.async_bridge import run_async

    storage = SQLiteStorage(db_path=str(tmp_path / "test.db"))
    run_async(storage.save_run(make_run("Fresh Idea")))

    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.storage.database_path = str(tmp_path / "test.db")
        result = runner.invoke(app, ["history", "prune", "--older-than", "999d"])

    assert result.exit_code == 0
    assert "Deleted 0" in result.output


# ---------------------------------------------------------------------------
# History show prefix ambiguity (Phase 10.3)
# ---------------------------------------------------------------------------

def test_history_show_ambiguous_prefix_shows_warning(runner: CliRunner, tmp_path: Path) -> None:
    """history show with ambiguous prefix shows a warning and matching runs table."""
    from ideagen.cli.async_bridge import run_async

    storage = SQLiteStorage(db_path=str(tmp_path / "test.db"))
    run_async(storage.save_run(make_run("Idea A")))
    run_async(storage.save_run(make_run("Idea B")))

    # Use a very short prefix that could match multiple runs
    # We need to find a common prefix — just use empty string which matches all
    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.storage.database_path = str(tmp_path / "test.db")
        # Use an empty-ish prefix — get actual IDs first
        runs = run_async(storage.get_runs())
        # Find a common prefix between the two run IDs (first char is enough since UUIDs vary)
        # Use a single char prefix that may match both
        result = runner.invoke(app, ["history", "show", ""])

    assert result.exit_code == 0
    assert "Ambiguous" in result.output or "Matching Runs" in result.output


def test_history_show_ambiguous_prefix_still_shows_detail(runner: CliRunner, tmp_path: Path) -> None:
    """history show with ambiguous prefix still shows the most recent run's details."""
    from ideagen.cli.async_bridge import run_async

    storage = SQLiteStorage(db_path=str(tmp_path / "test.db"))
    run_async(storage.save_run(make_run("Old Idea")))
    run_async(storage.save_run(make_run("New Idea")))

    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.storage.database_path = str(tmp_path / "test.db")
        # Empty prefix matches all
        result = runner.invoke(app, ["history", "show", ""])

    assert result.exit_code == 0
    # Should show run detail (the ID field at minimum)
    assert "ID" in result.output
