"""Tests for ideagen schedule commands."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ideagen.cli.app import app
from ideagen.cli.schedule_store import load_schedules, save_schedule, remove_schedule


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def schedule_file(tmp_path: Path) -> Path:
    return tmp_path / "schedules.toml"


def test_save_schedule_persists_to_toml(schedule_file: Path) -> None:
    """save_schedule creates a TOML file with the schedule entry."""
    schedule_id = save_schedule(
        {"frequency": "daily", "time": "09:00", "domain": "software"},
        path=schedule_file,
    )
    assert schedule_file.exists()
    assert len(schedule_id) == 8

    schedules = load_schedules(path=schedule_file)
    assert len(schedules) == 1
    assert schedules[0]["frequency"] == "daily"
    assert schedules[0]["id"] == schedule_id


def test_load_schedules_empty_file(tmp_path: Path) -> None:
    """Loading from non-existent file returns empty list."""
    schedules = load_schedules(path=tmp_path / "nope.toml")
    assert schedules == []


def test_remove_schedule_deletes_entry(schedule_file: Path) -> None:
    """remove_schedule removes the entry from TOML file."""
    sid = save_schedule(
        {"frequency": "daily", "time": "09:00", "domain": "software"},
        path=schedule_file,
    )
    assert remove_schedule(sid, path=schedule_file) is True
    assert load_schedules(path=schedule_file) == []


def test_remove_schedule_not_found(schedule_file: Path) -> None:
    """remove_schedule returns False for unknown ID."""
    assert remove_schedule("bogus", path=schedule_file) is False


def test_add_schedule_cli(runner: CliRunner, tmp_path: Path) -> None:
    """ideagen schedule add persists and prints confirmation."""
    schedule_file = tmp_path / "schedules.toml"
    with patch("ideagen.cli.schedule_store.install_cron", return_value=True):
        result = runner.invoke(
            app,
            ["schedule", "add", "--daily", "--time", "08:00", "--domain", "software", "--schedule-file", str(schedule_file)],
        )
    assert result.exit_code == 0
    assert "created" in result.output.lower()
    assert schedule_file.exists()


def test_list_schedules_cli_shows_entries(runner: CliRunner, tmp_path: Path) -> None:
    """ideagen schedule list shows persisted schedules."""
    schedule_file = tmp_path / "schedules.toml"
    save_schedule({"frequency": "daily", "time": "09:00", "domain": "software"}, path=schedule_file)

    result = runner.invoke(app, ["schedule", "list", "--schedule-file", str(schedule_file)])
    assert result.exit_code == 0
    assert "daily" in result.output
    assert "09:00" in result.output


def test_list_schedules_cli_empty(runner: CliRunner, tmp_path: Path) -> None:
    """ideagen schedule list with no schedules shows message."""
    schedule_file = tmp_path / "nope.toml"
    result = runner.invoke(app, ["schedule", "list", "--schedule-file", str(schedule_file)])
    assert result.exit_code == 0
    assert "No active schedules" in result.output


def test_remove_schedule_cli(runner: CliRunner, tmp_path: Path) -> None:
    """ideagen schedule remove deletes the entry."""
    schedule_file = tmp_path / "schedules.toml"
    sid = save_schedule({"frequency": "daily", "time": "09:00", "domain": "software"}, path=schedule_file)

    with patch("ideagen.cli.schedule_store.uninstall_cron", return_value=True):
        result = runner.invoke(app, ["schedule", "remove", sid, "--schedule-file", str(schedule_file)])

    assert result.exit_code == 0
    assert "removed" in result.output.lower()
    assert load_schedules(path=schedule_file) == []


def test_remove_schedule_cli_not_found(runner: CliRunner, tmp_path: Path) -> None:
    """ideagen schedule remove with bogus ID shows error."""
    schedule_file = tmp_path / "nope.toml"
    result = runner.invoke(app, ["schedule", "remove", "bogus", "--schedule-file", str(schedule_file)])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_cron_install_called(tmp_path: Path) -> None:
    """install_cron calls subprocess.run with crontab."""
    from ideagen.cli.schedule_store import install_cron

    schedule = {"id": "test1234", "frequency": "daily", "time": "09:00", "domain": "software"}

    with patch("ideagen.cli.schedule_store.subprocess.run") as mock_run:
        # First call: crontab -l returns existing
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        install_cron(schedule)

    assert mock_run.called
    # First call should be crontab -l, second should be crontab -
    calls = mock_run.call_args_list
    assert any("crontab" in str(c) for c in calls)
