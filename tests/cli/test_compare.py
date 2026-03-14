"""Tests for ideagen compare CLI command."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
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


def test_compare_shows_table(runner: CliRunner, tmp_path: Path) -> None:
    """ideagen compare <run1> <run2> displays comparison table."""
    from ideagen.cli.async_bridge import run_async

    storage = SQLiteStorage(db_path=str(tmp_path / "test.db"))
    run_a = make_run("Shared Idea")
    run_b = make_run("Different Idea")
    id_a = run_async(storage.save_run(run_a))
    id_b = run_async(storage.save_run(run_b))

    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.storage.database_path = str(tmp_path / "test.db")
        result = runner.invoke(app, ["compare", id_a, id_b])

    assert result.exit_code == 0
    assert "Comparison" in result.output


def test_compare_identical_runs(runner: CliRunner, tmp_path: Path) -> None:
    """Comparing a run to itself shows 'identical'."""
    from ideagen.cli.async_bridge import run_async

    storage = SQLiteStorage(db_path=str(tmp_path / "test.db"))
    run = make_run("Same Idea")
    run_id = run_async(storage.save_run(run))

    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.storage.database_path = str(tmp_path / "test.db")
        result = runner.invoke(app, ["compare", run_id, run_id])

    assert result.exit_code == 0
    assert "identical" in result.output.lower()


def test_compare_invalid_run1(runner: CliRunner, tmp_path: Path) -> None:
    """ideagen compare with bogus first run ID shows error."""
    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.storage.database_path = str(tmp_path / "test.db")
        result = runner.invoke(app, ["compare", "bogus1", "bogus2"])

    assert result.exit_code == 1
    assert "No run found" in result.output


def test_compare_invalid_run2(runner: CliRunner, tmp_path: Path) -> None:
    """ideagen compare with bogus second run ID shows error."""
    from ideagen.cli.async_bridge import run_async

    storage = SQLiteStorage(db_path=str(tmp_path / "test.db"))
    run_id = run_async(storage.save_run(make_run("Real Idea")))

    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.storage.database_path = str(tmp_path / "test.db")
        result = runner.invoke(app, ["compare", run_id, "bogus2"])

    assert result.exit_code == 1
    assert "No run found" in result.output
