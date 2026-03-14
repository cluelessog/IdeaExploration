"""Schedule persistence via TOML file + cron job management."""
from __future__ import annotations

import logging
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

import tomli_w

logger = logging.getLogger("ideagen")

SCHEDULE_FILE = Path("~/.ideagen/schedules.toml")


def _schedule_path(path: Path | None = None) -> Path:
    return (path or SCHEDULE_FILE).expanduser()


def load_schedules(path: Path | None = None) -> list[dict]:
    """Load all schedules from TOML file."""
    import tomllib

    p = _schedule_path(path)
    if not p.exists():
        return []

    with open(p, "rb") as f:
        data = tomllib.load(f)

    return data.get("schedules", [])


def save_schedule(schedule: dict, path: Path | None = None) -> str:
    """Append a schedule and return its generated ID."""
    p = _schedule_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    schedules = load_schedules(path)
    schedule_id = str(uuid.uuid4())[:8]
    schedule["id"] = schedule_id
    schedule["created_at"] = datetime.now().isoformat()
    schedules.append(schedule)

    with open(p, "wb") as f:
        tomli_w.dump({"schedules": schedules}, f)

    return schedule_id


def remove_schedule(schedule_id: str, path: Path | None = None) -> bool:
    """Remove a schedule by ID. Returns True if found and removed."""
    p = _schedule_path(path)
    schedules = load_schedules(path)
    original_len = len(schedules)
    schedules = [s for s in schedules if s.get("id") != schedule_id]

    if len(schedules) == original_len:
        return False

    with open(p, "wb") as f:
        tomli_w.dump({"schedules": schedules}, f)

    return True


def _build_cron_expression(frequency: str, time_str: str) -> str:
    """Convert frequency + time to cron expression."""
    hour, minute = time_str.split(":")
    if frequency == "daily":
        return f"{minute} {hour} * * *"
    elif frequency == "weekly":
        return f"{minute} {hour} * * 1"  # Monday
    return f"{minute} {hour} * * *"  # default to daily


def _find_ideagen_bin() -> str:
    """Find the ideagen executable path."""
    import shutil
    path = shutil.which("ideagen")
    return path or "ideagen"


def is_wsl() -> bool:
    """Detect if running under Windows Subsystem for Linux."""
    try:
        with open("/proc/version", "r") as f:
            return "microsoft" in f.read().lower()
    except (FileNotFoundError, PermissionError):
        return False


def install_cron(schedule: dict) -> bool:
    """Install a cron job for the schedule. Returns True on success."""
    if sys.platform == "win32":
        return False

    if is_wsl():
        logger.warning(
            "WSL detected. crontab may not persist across reboots. "
            "Consider using Windows Task Scheduler (schtasks) or systemd timers instead."
        )

    tag = f"# ideagen-{schedule['id']}"
    cron_expr = _build_cron_expression(schedule["frequency"], schedule["time"])
    ideagen_bin = _find_ideagen_bin()
    cron_line = f"{cron_expr} {ideagen_bin} run --domain {schedule['domain']} {tag}"

    try:
        # Read existing crontab
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True
        )
        existing = result.stdout if result.returncode == 0 else ""

        # Append new line
        new_crontab = existing.rstrip("\n") + "\n" + cron_line + "\n"

        # Write back
        subprocess.run(
            ["crontab", "-"], input=new_crontab, text=True, check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def uninstall_cron(schedule_id: str) -> bool:
    """Remove the cron entry for the given schedule ID. Returns True on success."""
    if sys.platform == "win32":
        return False

    tag = f"ideagen-{schedule_id}"

    try:
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True
        )
        if result.returncode != 0:
            return False

        lines = result.stdout.splitlines()
        filtered = [line for line in lines if tag not in line]

        if len(filtered) == len(lines):
            return False  # Not found

        new_crontab = "\n".join(filtered) + "\n"
        subprocess.run(
            ["crontab", "-"], input=new_crontab, text=True, check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
