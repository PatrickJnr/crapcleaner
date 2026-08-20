"""Support diagnostics bundle: one text file a user can attach to a bug report.

Every filesystem path is reduced to its root before being written. Directory and file
names identify people and their work, and a bundle is meant to be shared.
"""

import os
import platform
import re
from datetime import datetime

from crapcleaner import __version__
from crapcleaner.config import load_settings
from crapcleaner.registry import get_all_categories
from crapcleaner.system.capabilities import capability_summary
from crapcleaner.utils.format import format_size
from crapcleaner.utils.logs import log_path
from crapcleaner.utils.platform import get_drive_info, is_admin, list_drives

LOG_TAIL_LINES = 200

_PATH = re.compile(r"[A-Za-z]:[\\/][^\s'\"]*|(?<![\w.:])/[^\s'\"]*")


def _redact(text: str) -> str:
    """Reduce every path in `text` to its root."""
    return _PATH.sub(lambda m: m.group(0)[:2] + "\\" if m.group(0)[1:2] == ":" else "/", text)


def _log_tail() -> list[str]:
    try:
        with open(log_path(), encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError as exc:
        return [f"(log unavailable: {_redact(str(exc))})"]
    return [line.rstrip() for line in lines[-LOG_TAIL_LINES:]]


def build_diagnostics_text() -> str:
    """The bundle contents, with every path already redacted to its root."""
    settings = load_settings()
    lines = [
        "=== CrapCleaner Diagnostics ===",
        f"Generated:   {datetime.now().isoformat(timespec='seconds')}",
        f"Version:     v{__version__}",
        f"OS:          {platform.system()} {platform.release()} ({platform.machine()})",
        f"Python:      {platform.python_version()}",
        f"Admin:       {'Yes' if is_admin() else 'No'}",
        f"Categories:  {len(get_all_categories())} loaded",
        f"Exclusions:  {len(settings.get('excluded_paths', []))} rules",
        "",
        "--- Capabilities ---",
    ]

    for key, cap in capability_summary().items():
        state = "supported" if cap["supported"] else f"unsupported ({cap['reason'] or 'no reason'})"
        lines.append(f"{key}: {state}")

    lines += ["", "--- Drives ---"]
    for drive in list_drives():
        try:
            info = get_drive_info(drive)
        except OSError as exc:
            lines.append(f"{drive}  unreadable ({exc})")
            continue
        total = int(info.get("total", 0))
        free = int(info.get("free", 0))
        lines.append(
            f"{drive}  {format_size(free)} free of {format_size(total)} "
            f"({info.get('filesystem', 'unknown')})"
        )

    lines += ["", f"--- Log (last {LOG_TAIL_LINES} lines) ---"]
    lines += _log_tail()
    return _redact("\n".join(lines)) + "\n"


def write_diagnostics_bundle(destination: str) -> str:
    """Write the diagnostics bundle to `destination` and return the path written."""
    parent = os.path.dirname(os.path.abspath(destination))
    os.makedirs(parent, exist_ok=True)
    with open(destination, "w", encoding="utf-8") as fh:
        fh.write(build_diagnostics_text())
    return destination
