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
