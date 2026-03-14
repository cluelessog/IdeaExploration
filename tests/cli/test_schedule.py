"""Tests for ideagen schedule commands."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
from typer.testing import CliRunner

from ideagen.cli.app import app
from ideagen.cli.schedule_store import (
    _build_cron_expression,
    _find_ideagen_bin,
    install_cron,
    load_schedules,
    remove_schedule,
    save_schedule,
    uninstall_cron,
)


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
    # Verify the cron line written includes the ideagen command and schedule tag
    write_call = calls[-1]
    written_input = write_call.kwargs.get("input", "") or ""
    assert "ideagen" in written_input
    assert "ideagen-test1234" in written_input


# ---------------------------------------------------------------------------
# _build_cron_expression tests
# ---------------------------------------------------------------------------

def test_build_cron_expression_daily() -> None:
    """Daily frequency produces correct cron expression."""
    assert _build_cron_expression("daily", "09:30") == "30 09 * * *"


def test_build_cron_expression_weekly() -> None:
    """Weekly frequency produces Monday cron expression."""
    assert _build_cron_expression("weekly", "14:00") == "00 14 * * 1"


def test_build_cron_expression_unknown_defaults_daily() -> None:
    """Unknown frequency defaults to daily cron expression."""
    assert _build_cron_expression("monthly", "08:00") == "00 08 * * *"


# ---------------------------------------------------------------------------
# _find_ideagen_bin tests
# ---------------------------------------------------------------------------

def test_find_ideagen_bin_found() -> None:
    """Returns the path when shutil.which finds ideagen."""
    with patch("shutil.which", return_value="/usr/local/bin/ideagen"):
        result = _find_ideagen_bin()
    assert result == "/usr/local/bin/ideagen"


def test_find_ideagen_bin_not_found() -> None:
    """Falls back to 'ideagen' when shutil.which returns None."""
    with patch("shutil.which", return_value=None):
        result = _find_ideagen_bin()
    assert result == "ideagen"


# ---------------------------------------------------------------------------
# install_cron tests
# ---------------------------------------------------------------------------

def test_install_cron_windows_returns_false() -> None:
    """install_cron returns False on Windows without calling subprocess."""
    schedule = {"id": "abc12345", "frequency": "daily", "time": "09:00", "domain": "software"}
    with patch("ideagen.cli.schedule_store.sys") as mock_sys:
        mock_sys.platform = "win32"
        result = install_cron(schedule)
    assert result is False


def test_install_cron_crontab_fails_returns_false() -> None:
    """install_cron returns False when subprocess raises CalledProcessError."""
    schedule = {"id": "abc12345", "frequency": "daily", "time": "09:00", "domain": "software"}
    with patch("ideagen.cli.schedule_store.sys") as mock_sys, \
         patch("ideagen.cli.schedule_store.subprocess.run") as mock_run:
        mock_sys.platform = "linux"
        mock_run.side_effect = subprocess.CalledProcessError(1, "crontab")
        result = install_cron(schedule)
    assert result is False


def test_install_cron_no_existing_crontab() -> None:
    """install_cron returns True when crontab -l returns non-zero (no existing crontab)."""
    schedule = {"id": "new12345", "frequency": "daily", "time": "10:00", "domain": "software"}

    list_result = MagicMock()
    list_result.returncode = 1
    list_result.stdout = ""

    write_result = MagicMock()
    write_result.returncode = 0

    with patch("ideagen.cli.schedule_store.sys") as mock_sys, \
         patch("ideagen.cli.schedule_store.subprocess.run") as mock_run:
        mock_sys.platform = "linux"
        mock_run.side_effect = [list_result, write_result]
        result = install_cron(schedule)

    assert result is True


# ---------------------------------------------------------------------------
# uninstall_cron tests
# ---------------------------------------------------------------------------

def test_uninstall_cron_success() -> None:
    """uninstall_cron returns True when the schedule tag is present in crontab."""
    existing_crontab = "0 9 * * * ideagen run --domain software # ideagen-test1234\n"

    list_result = MagicMock()
    list_result.returncode = 0
    list_result.stdout = existing_crontab

    write_result = MagicMock()
    write_result.returncode = 0

    with patch("ideagen.cli.schedule_store.sys") as mock_sys, \
         patch("ideagen.cli.schedule_store.subprocess.run") as mock_run:
        mock_sys.platform = "linux"
        mock_run.side_effect = [list_result, write_result]
        result = uninstall_cron("test1234")

    assert result is True


def test_uninstall_cron_not_found() -> None:
    """uninstall_cron returns False when no matching schedule tag exists."""
    existing_crontab = "0 9 * * * ideagen run --domain software # ideagen-other999\n"

    list_result = MagicMock()
    list_result.returncode = 0
    list_result.stdout = existing_crontab

    with patch("ideagen.cli.schedule_store.sys") as mock_sys, \
         patch("ideagen.cli.schedule_store.subprocess.run") as mock_run:
        mock_sys.platform = "linux"
        mock_run.return_value = list_result
        result = uninstall_cron("test1234")

    assert result is False


def test_uninstall_cron_windows_returns_false() -> None:
    """uninstall_cron returns False on Windows."""
    with patch("ideagen.cli.schedule_store.sys") as mock_sys:
        mock_sys.platform = "win32"
        result = uninstall_cron("anyid")
    assert result is False


def test_uninstall_cron_crontab_error() -> None:
    """uninstall_cron returns False when crontab -l raises an error."""
    with patch("ideagen.cli.schedule_store.sys") as mock_sys, \
         patch("ideagen.cli.schedule_store.subprocess.run") as mock_run:
        mock_sys.platform = "linux"
        mock_run.side_effect = subprocess.CalledProcessError(1, "crontab")
        result = uninstall_cron("anyid")
    assert result is False


# ---------------------------------------------------------------------------
# WSL detection tests (Phase 10.4)
# ---------------------------------------------------------------------------

from ideagen.cli.schedule_store import is_wsl


def test_is_wsl_detects_wsl_proc_version() -> None:
    """is_wsl returns True when /proc/version contains 'microsoft'."""
    mock_content = "Linux version 5.15.0-1-microsoft-standard-WSL2"
    with patch("builtins.open", mock_open(read_data=mock_content)):
        assert is_wsl() is True


def test_is_wsl_false_on_native_linux() -> None:
    """is_wsl returns False on native Linux."""
    mock_content = "Linux version 6.1.0-generic (buildd@lcy02)"
    with patch("builtins.open", mock_open(read_data=mock_content)):
        assert is_wsl() is False


def test_is_wsl_false_when_file_missing() -> None:
    """is_wsl returns False when /proc/version doesn't exist."""
    with patch("builtins.open", side_effect=FileNotFoundError):
        assert is_wsl() is False


def test_install_cron_wsl_logs_warning() -> None:
    """install_cron logs a WSL warning when WSL is detected."""
    schedule = {"id": "wsl12345", "frequency": "daily", "time": "09:00", "domain": "software"}

    list_result = MagicMock()
    list_result.returncode = 0
    list_result.stdout = ""
    write_result = MagicMock()
    write_result.returncode = 0

    with patch("ideagen.cli.schedule_store.is_wsl", return_value=True), \
         patch("ideagen.cli.schedule_store.sys") as mock_sys, \
         patch("ideagen.cli.schedule_store.subprocess.run") as mock_run, \
         patch("ideagen.cli.schedule_store.logger") as mock_logger:
        mock_sys.platform = "linux"
        mock_run.side_effect = [list_result, write_result]
        install_cron(schedule)

    mock_logger.warning.assert_called_once()
    warning_msg = mock_logger.warning.call_args[0][0]
    assert "WSL" in warning_msg
    assert "schtasks" in warning_msg or "systemd" in warning_msg


def test_install_cron_wsl_still_attempts_cron() -> None:
    """install_cron still attempts cron installation on WSL (doesn't bail out)."""
    schedule = {"id": "wsl12345", "frequency": "daily", "time": "09:00", "domain": "software"}

    list_result = MagicMock()
    list_result.returncode = 0
    list_result.stdout = ""
    write_result = MagicMock()
    write_result.returncode = 0

    with patch("ideagen.cli.schedule_store.is_wsl", return_value=True), \
         patch("ideagen.cli.schedule_store.sys") as mock_sys, \
         patch("ideagen.cli.schedule_store.subprocess.run") as mock_run:
        mock_sys.platform = "linux"
        mock_run.side_effect = [list_result, write_result]
        result = install_cron(schedule)

    assert result is True
    assert mock_run.call_count == 2  # crontab -l and crontab -
