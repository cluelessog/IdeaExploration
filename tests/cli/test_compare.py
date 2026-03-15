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


def test_compare_ambiguous_prefix_shows_warning(runner: CliRunner, tmp_path: Path) -> None:
    """Ambiguous prefix matching 2 runs shows warning and uses most recent."""
    from ideagen.cli.async_bridge import run_async
    from datetime import datetime, timedelta

    storage = SQLiteStorage(db_path=str(tmp_path / "test.db"))
    # Save two runs with different timestamps; we'll use a prefix that matches both
    run_a = make_run("Idea A", timestamp=datetime(2024, 1, 1))
    run_b = make_run("Idea B", timestamp=datetime(2024, 1, 2))
    id_a = run_async(storage.save_run(run_a))
    id_b = run_async(storage.save_run(run_b))

    # A prefix of empty string matches all; use real prefix of shared chars
    # Instead, patch find_runs_by_prefix to return two fake matches so we
    # control the ambiguity without needing shared UUID prefixes.
    shared_prefix = id_a[:4]

    # Save a second run whose ID happens to share the same first 4 chars is not
    # guaranteed, so we patch storage.find_runs_by_prefix instead.
    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.storage.database_path = str(tmp_path / "test.db")
        with patch("ideagen.storage.sqlite.SQLiteStorage.find_runs_by_prefix") as mock_prefix:
            # Return two matches — most-recent first (id_b is newer)
            mock_prefix.return_value = [
                {"id": id_b, "timestamp": "2024-01-02T00:00:00", "domain": "software_saas"},
                {"id": id_a, "timestamp": "2024-01-01T00:00:00", "domain": "software_saas"},
            ]
            result = runner.invoke(app, ["compare", shared_prefix, id_b])

    assert result.exit_code == 0
    assert "Ambiguous" in result.output


def test_compare_exact_match_no_warning(runner: CliRunner, tmp_path: Path) -> None:
    """Full run ID (exact match) produces no ambiguity warning."""
    from ideagen.cli.async_bridge import run_async

    storage = SQLiteStorage(db_path=str(tmp_path / "test.db"))
    run_a = make_run("Idea A")
    run_b = make_run("Idea B")
    id_a = run_async(storage.save_run(run_a))
    id_b = run_async(storage.save_run(run_b))

    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.storage.database_path = str(tmp_path / "test.db")
        result = runner.invoke(app, ["compare", id_a, id_b])

    assert result.exit_code == 0
    assert "Ambiguous" not in result.output


def test_compare_no_match_shows_error(runner: CliRunner, tmp_path: Path) -> None:
    """Prefix matching no runs shows a clear error and exits non-zero."""
    with patch("ideagen.cli.config_loader.load_config") as mock_config:
        mock_config.return_value.storage.database_path = str(tmp_path / "test.db")
        result = runner.invoke(app, ["compare", "nonexistent-prefix", "another-prefix"])

    assert result.exit_code == 1
    assert "No run found" in result.output
