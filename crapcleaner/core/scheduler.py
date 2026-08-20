"""Scheduled, non-destructive scans, run by the operating system's own scheduler.

**A scheduled run never deletes anything.** It scans, writes the result where the
application can find it, and says so.

Scheduling is delegated to the OS - Task Scheduler on Windows, a systemd user timer
on Linux - rather than a background service of ours: nothing of ours runs between
scans, the schedule is visible in the tools people already use to audit what runs on
their machine, and uninstalling leaves no daemon behind.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from dataclasses import asdict, dataclass

from crapcleaner.utils.logs import get_logger
from crapcleaner.utils.platform import is_linux, is_windows, run_command

logger = get_logger("scheduler")

TASK_NAME = "CrapCleaner Scan"
UNIT_NAME = "crapcleaner-scan"
RESULT_FILE = "scheduled_scan.json"
DEFAULT_TIME = "18:00"


@dataclass(frozen=True)
class ScheduleConfig:
    """What the user asked for."""

    enabled: bool = False
    #: 24-hour local time, "HH:MM".
    at: str = DEFAULT_TIME
    #: "daily" or "weekly".
    frequency: str = "daily"
    #: Notify when this much is reclaimable. 0 means always report.
    threshold_mb: int = 5120

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_settings(cls, settings: dict) -> ScheduleConfig:
        raw = settings.get("schedule", {}) or {}
        return cls(
            enabled=bool(raw.get("enabled", False)),
            at=str(raw.get("at", DEFAULT_TIME)),
            frequency=str(raw.get("frequency", "daily")),
            threshold_mb=int(raw.get("threshold_mb", 5120)),
        )


@dataclass(frozen=True)
class ScheduleStatus:
    """What the operating system actually has registered."""

    supported: bool
    registered: bool
    detail: str
    config: ScheduleConfig
    command: str = ""

    def to_dict(self) -> dict:
        return {
            "supported": self.supported,
            "registered": self.registered,
            "detail": self.detail,
            "command": self.command,
            "config": self.config.to_dict(),
        }


def _valid_time(at: str) -> str:
    """Accept only HH:MM, so nothing user-supplied reaches a command line unchecked."""
    parts = at.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(f"Not a 24-hour time: {at!r}")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Not a 24-hour time: {at!r}")
    return f"{hour:02d}:{minute:02d}"


def launch_command() -> list[str]:
    """How the scheduler should invoke this application.

    A frozen build is launched directly; from source it needs the interpreter.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "scheduled-scan"]
    return [sys.executable, "-m", "crapcleaner", "scheduled-scan"]


def _quoted_command() -> str:
    parts = launch_command()
    return " ".join(f'"{p}"' if " " in p else p for p in parts)


def result_path() -> str:
    from crapcleaner.config import config_dir

    return os.path.join(config_dir(), RESULT_FILE)


# --------------------------------------------------------------------- status
def is_supported() -> bool:
    if is_windows():
        return shutil.which("schtasks") is not None
    if is_linux():
        return shutil.which("systemctl") is not None
    return False


def _systemd_dir() -> str:
    from crapcleaner.utils.platform import get_user_profile

    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(get_user_profile(), ".config")
    return os.path.join(base, "systemd", "user")


def status() -> ScheduleStatus:
    """Whether a schedule is registered right now, asked of the OS."""
    from crapcleaner.config import load_settings

    config = ScheduleConfig.from_settings(load_settings())
    if not is_supported():
        missing = "schtasks" if is_windows() else "systemctl"
        return ScheduleStatus(
            supported=False,
            registered=False,
            detail=f"Scheduling needs {missing}, which is not available here.",
            config=config,
        )

    if is_windows():
        result = run_command(["schtasks", "/Query", "/TN", TASK_NAME], timeout=20.0)
        registered = result.returncode == 0
        detail = f"Task Scheduler entry {TASK_NAME!r}" if registered else "No scheduled task."
    else:
        timer = os.path.join(_systemd_dir(), f"{UNIT_NAME}.timer")
        result = run_command(
            ["systemctl", "--user", "is-enabled", f"{UNIT_NAME}.timer"], timeout=20.0
        )
        registered = os.path.isfile(timer) and result.returncode == 0
        detail = f"systemd user timer {UNIT_NAME}.timer" if registered else "No timer installed."

    return ScheduleStatus(
        supported=True,
        registered=registered,
        detail=detail,
        config=config,
        command=_quoted_command(),
    )


# ---------------------------------------------------------------- registration
def enable(config: ScheduleConfig) -> tuple[bool, str]:
    """Register the schedule with the operating system and store the settings."""
    if not is_supported():
        return False, status().detail

    at = _valid_time(config.at)
    if is_windows():
        ok, message = _enable_windows(at, config.frequency)
    else:
        ok, message = _enable_linux(at, config.frequency)

    if ok:
        _store(config.__class__(**{**config.to_dict(), "enabled": True, "at": at}))
    return ok, message


def disable() -> tuple[bool, str]:
    """Remove the schedule. Settings keep the rest of the configuration."""
    if is_windows():
        result = run_command(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"], timeout=20.0)
        ok = result.returncode == 0 or "cannot find" in (result.stderr or "").lower()
        message = "Scheduled scan removed." if ok else result.stderr.strip()
    elif is_linux():
        run_command(["systemctl", "--user", "disable", "--now", f"{UNIT_NAME}.timer"], timeout=20.0)
        for suffix in (".timer", ".service"):
            try:
                os.remove(os.path.join(_systemd_dir(), f"{UNIT_NAME}{suffix}"))
            except OSError:
                pass
        run_command(["systemctl", "--user", "daemon-reload"], timeout=20.0)
        ok, message = True, "Scheduled scan removed."
    else:
        return False, "Scheduling is not supported on this platform."

    from crapcleaner.config import load_settings

    current = ScheduleConfig.from_settings(load_settings())
    _store(ScheduleConfig(**{**current.to_dict(), "enabled": False}))
    return ok, message


def _store(config: ScheduleConfig) -> None:
    from crapcleaner.config import update_settings

    update_settings(schedule=config.to_dict())


def _enable_windows(at: str, frequency: str) -> tuple[bool, str]:
    schedule = "WEEKLY" if frequency == "weekly" else "DAILY"
    result = run_command(
        [
            "schtasks",
            "/Create",
            "/TN",
            TASK_NAME,
            "/TR",
            _quoted_command(),
            "/SC",
            schedule,
            "/ST",
            at,
            "/F",
        ],
        timeout=30.0,
    )
    if result.returncode == 0:
        return True, f"Scheduled a {schedule.lower()} scan at {at}."
    return False, (result.stderr or result.stdout or "schtasks refused the request.").strip()


_SERVICE_UNIT = """[Unit]
Description=CrapCleaner scheduled scan (read-only; never deletes anything)

[Service]
Type=oneshot
ExecStart={command}
"""

_TIMER_UNIT = """[Unit]
Description=Run the CrapCleaner scan on a schedule

[Timer]
OnCalendar={calendar}
Persistent=true

[Install]
WantedBy=timers.target
"""


def _enable_linux(at: str, frequency: str) -> tuple[bool, str]:
    directory = _systemd_dir()
    calendar = f"Mon *-*-* {at}:00" if frequency == "weekly" else f"*-*-* {at}:00"
    try:
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, f"{UNIT_NAME}.service"), "w", encoding="utf-8") as fh:
            fh.write(_SERVICE_UNIT.format(command=" ".join(launch_command())))
        with open(os.path.join(directory, f"{UNIT_NAME}.timer"), "w", encoding="utf-8") as fh:
            fh.write(_TIMER_UNIT.format(calendar=calendar))
    except OSError as exc:
        return False, f"Could not write the timer units: {exc}"

    run_command(["systemctl", "--user", "daemon-reload"], timeout=20.0)
    result = run_command(
        ["systemctl", "--user", "enable", "--now", f"{UNIT_NAME}.timer"], timeout=20.0
    )
    if result.returncode == 0:
        return True, f"Scheduled a {frequency} scan at {at}."
    return False, (result.stderr or "systemctl refused to enable the timer.").strip()


# ------------------------------------------------------------------- the run
def run_scheduled_scan(config: ScheduleConfig | None = None) -> dict:
    """Scan, record the result, and notify if it is worth the interruption.

    Never cleans: an unattended run must not delete without a person having looked.
    """
    from crapcleaner.config import load_settings
    from crapcleaner.core.scanner import ScanEngine
    from crapcleaner.registry import get_all_categories

    settings = load_settings()
    config = config or ScheduleConfig.from_settings(settings)

    disabled = set(settings.get("disabled_categories", []))
    categories = [c for c in get_all_categories() if c.id not in disabled]
    report = ScanEngine(categories).run(max_files=settings.get("max_scan_files", 200000))

    threshold_bytes = max(0, config.threshold_mb) * 1024 * 1024
    exceeded = report.total_size >= threshold_bytes if threshold_bytes else report.total_size > 0

    result = {
        "finished_at": time.time(),
        "total_reclaimable": report.total_size,
        "total_files": report.total_files,
        "threshold_bytes": threshold_bytes,
        "threshold_exceeded": exceeded,
        "duration": report.duration,
        "top_categories": [
            {"id": r.category_id, "name": r.name, "size": r.size}
            for r in sorted(report.results, key=lambda r: r.size, reverse=True)[:10]
            if r.size > 0
        ],
    }

    try:
        path = result_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    except OSError:
        logger.warning("Could not record the scheduled scan result", exc_info=True)

    if exceeded:
        notify(report.total_size)
    return result


def last_result() -> dict | None:
    """The most recent scheduled scan, for the interface to surface."""
    try:
        with open(result_path(), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def notify(reclaimable_bytes: int) -> bool:
    """Tell the user, using whatever the desktop provides. Never fatal."""
    from crapcleaner.utils.format import format_size

    message = f"{format_size(reclaimable_bytes)} of reclaimable space found."
    if is_linux() and shutil.which("notify-send"):
        return run_command(
            ["notify-send", "-a", "CrapCleaner", "CrapCleaner", message], timeout=10.0
        ).ok
    if is_windows() and shutil.which("msg.exe"):
        # Pro editions only, but the one notification path needing nothing installed.
        run_command(["msg.exe", "*", "/TIME:60", f"CrapCleaner: {message}"], timeout=10.0)
    logger.info("Scheduled scan: %s", message)
    return True
