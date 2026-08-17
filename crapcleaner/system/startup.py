"""Startup Manager - platform-neutral dispatcher.

Holds the shared :class:`StartupItem` model and the platform-independent heuristics
(impact estimation, publisher inference, command parsing), then routes each operation
to the backend for the running operating system:

* Windows -> :mod:`crapcleaner.system.backends.startup_windows` (registry Run keys,
  Startup folders, StartupApproved flags)
* Linux   -> :mod:`crapcleaner.system.backends.startup_linux` (XDG autostart entries)

An item id encodes which backend owns it (``reg:``/``folder:`` on Windows, ``linux:``
on Linux), so a stale id from another platform is rejected rather than acted on.
"""

import os
import re
import shlex
from dataclasses import dataclass
from typing import Any

from crapcleaner.system.capabilities import STARTUP, get_capability


@dataclass
class StartupItem:
    """One auto-start entry, described identically on every platform."""

    id: str
    name: str
    command: str
    location: str
    # Windows: HKCU_RUN, HKLM_RUN, HKCU_RUNONCE, HKLM_RUNONCE, USER_STARTUP, COMMON_STARTUP
    # Linux:   USER_STARTUP, COMMON_STARTUP
    location_key: str
    scope: str  # USER, SYSTEM
    enabled: bool
    impact: str  # High, Medium, Low, Not Measured
    publisher: str
    file_path: str
    file_exists: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "command": self.command,
            "location": self.location,
            "location_key": self.location_key,
            "scope": self.scope,
            "enabled": self.enabled,
            "impact": self.impact,
            "publisher": self.publisher,
            "file_path": self.file_path,
            "file_exists": self.file_exists,
        }


# ---------------------------------------------------------------------------
# Shared heuristics - no platform branching
# ---------------------------------------------------------------------------


def extract_executable_path(command: str) -> str:
    """Extract the target executable from a command line."""
    cmd = command.strip()
    if not cmd:
        return ""
    if cmd.startswith('"'):
        end_idx = cmd.find('"', 1)
        if end_idx != -1:
            return cmd[1:end_idx].strip()
    try:
        parts = shlex.split(cmd, posix=False)
        if parts:
            return parts[0].strip("\"'>")
    except Exception:
        pass
    if " " in cmd:
        return cmd.split(" ")[0].strip("\"'>")
    return cmd.strip("\"'>")


_HIGH_IMPACT_KEYWORDS = (
    "discord", "steam", "epicgames", "spotify", "teams", "slack", "creative cloud",
    "adobe", "chrome", "edge", "browser", "origin", "battle.net", "overwolf", "docker",
)

_MEDIUM_IMPACT_KEYWORDS = (
    "onedrive", "dropbox", "googledrive", "syncthing", "antivirus", "security",
    "razer", "logitech", "corsair", "icue", "nvidia", "amd", "realtek",
)


def estimate_startup_impact(name: str, file_path: str, file_exists: bool) -> str:
    """Estimate boot impact (High, Medium, Low, Not Measured) from name, path, size."""
    if not file_exists or not file_path:
        return "Not Measured"

    haystack = (name.lower(), file_path.lower())
    if any(k in haystack[0] or k in haystack[1] for k in _HIGH_IMPACT_KEYWORDS):
        return "High"
    if any(k in haystack[0] or k in haystack[1] for k in _MEDIUM_IMPACT_KEYWORDS):
        return "Medium"

    try:
        if os.path.isfile(file_path):
            size = os.path.getsize(file_path)
            if size > 30 * 1024 * 1024:
                return "High"
            if size > 5 * 1024 * 1024:
                return "Medium"
            return "Low"
    except OSError:
        pass

    return "Low"


_PUBLISHER_SIGNATURES = (
    (("microsoft", "windows"), "Microsoft Corporation"),
    (("google", "chrome"), "Google LLC"),
    (("discord",), "Discord Inc."),
    (("spotify",), "Spotify AB"),
    (("steam", "valve"), "Valve Corporation"),
    (("epic games", "epicgames"), "Epic Games, Inc."),
    (("adobe",), "Adobe Inc."),
    (("nvidia",), "NVIDIA Corporation"),
    (("intel",), "Intel Corporation"),
    (("amd", "advanced micro devices"), "Advanced Micro Devices, Inc."),
    (("razer",), "Razer Inc."),
    (("logitech", "lghub"), "Logitech"),
    (("apple",), "Apple Inc."),
)


def extract_publisher(name: str, file_path: str) -> str:
    """Infer a publisher from an entry name or executable path."""
    name_lower = name.lower()
    path_lower = file_path.lower()

    for keywords, publisher in _PUBLISHER_SIGNATURES:
        if any(k in name_lower or k in path_lower for k in keywords):
            return publisher

    match = re.search(r"program files(?: \(x86\))?[\\/]([^\\/]+)", path_lower)
    if match:
        folder_name = match.group(1).capitalize()
        if folder_name not in ("Common files", "Windows defender"):
            return folder_name

    return "Unknown Publisher"


# Historic private aliases - imported by tests and older call sites.
_extract_executable_path = extract_executable_path
_estimate_startup_impact = estimate_startup_impact
_extract_publisher = extract_publisher


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def _backend():
    """The startup backend for the running platform, or None when unsupported."""
    cap = get_capability(STARTUP)
    if not cap.supported:
        return None
    if cap.platform == "windows":
        from crapcleaner.system.backends import startup_windows

        return startup_windows
    from crapcleaner.system.backends import startup_linux

    return startup_linux


def _unsupported() -> str:
    return get_capability(STARTUP).unsupported_reason or "Startup management is unavailable."


def is_available() -> bool:
    """Whether this platform can manage startup entries at all."""
    return _backend() is not None


def add_scopes() -> tuple[str, ...]:
    """Scopes the platform accepts for new entries, for populating the Add dialog."""
    backend = _backend()
    return backend.ADD_SCOPES if backend else ()


#: Item id prefixes each platform owns, used to reject ids from another platform.
_OWNED_PREFIXES = {"windows": ("reg", "folder"), "linux": ("linux",)}


def _split_id(item_id: str) -> tuple[str, str, str] | None:
    parts = item_id.split(":", 2)
    if len(parts) < 3 or not all(parts):
        return None
    return parts[0], parts[1], parts[2]


def _resolve(item_id: str):
    """Validate an item id against the running platform and return its backend."""
    parsed = _split_id(item_id)
    if parsed is None:
        return None, (False, "Invalid startup item identifier.")

    backend = _backend()
    if backend is None:
        return None, (False, _unsupported())

    kind = parsed[0]
    platform = get_capability(STARTUP).platform
    if kind not in _OWNED_PREFIXES.get(platform, ()):
        return None, (False, f"Startup entry '{item_id}' does not belong to this operating system.")

    return (backend, parsed), None


def get_startup_items(force_refresh: bool = False) -> list[StartupItem]:
    """Retrieve every configured startup entry for the running platform."""
    backend = _backend()
    if backend is None:
        return []
    try:
        items = backend.list_items()
    except Exception:
        return []
    items.sort(key=lambda x: (not x.enabled, x.name.lower()))
    return items


def set_startup_item_enabled(item_id: str, enabled: bool) -> tuple[bool, str]:
    """Enable or disable a startup entry by id."""
    resolved, refusal = _resolve(item_id)
    if refusal:
        return refusal
    backend, (kind, loc_key, entry_name) = resolved
    return backend.set_enabled(kind, loc_key, entry_name, enabled)


def remove_startup_item(item_id: str) -> tuple[bool, str]:
    """Permanently remove a startup entry by id."""
    resolved, refusal = _resolve(item_id)
    if refusal:
        return refusal
    backend, (kind, loc_key, entry_name) = resolved
    return backend.remove(kind, loc_key, entry_name)


def add_startup_item(name: str, command: str, scope: str = "USER") -> tuple[bool, str]:
    """Register a new startup entry for the current user or, where allowed, the system."""
    clean_name = name.strip()
    clean_cmd = command.strip()
    if not clean_name or not clean_cmd:
        return False, "Application name and command line path must not be empty."

    backend = _backend()
    if backend is None:
        return False, _unsupported()

    if scope.upper() not in backend.ADD_SCOPES:
        allowed = ", ".join(backend.ADD_SCOPES).lower()
        return False, f"This operating system only supports adding {allowed}-scope startup entries."

    return backend.add(clean_name, clean_cmd, scope)
