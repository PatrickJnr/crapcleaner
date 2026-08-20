"""Platform capability registry.

Single source of truth for which system-management features the running operating
system provides, and for the wording each platform uses to describe them. The GUI,
the CLI, and the dispatching backends all read from here, so adding an operating
system means adding one entry per capability rather than hunting for `is_windows()`
checks scattered through the UI.

A capability is *supported* when the current platform has both an implementation and
the tooling it depends on (systemd's ``systemctl``, for instance). Unsupported
capabilities are hidden from the navigation rail and rejected with an explanation by
the dispatchers in :mod:`crapcleaner.system.services`,
:mod:`crapcleaner.system.startup`, and :mod:`crapcleaner.system.system_updates`.
"""

import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from crapcleaner.utils.platform import is_linux, is_windows

# Capability keys. These double as GUI page keys and as navigation identifiers.
STARTUP = "startup"
SERVICES = "services"
SYSTEM_UPDATES = "updates"
APP_UPDATES = "app_updates"


@dataclass(frozen=True)
class Capability:
    """What one system-management feature is called, and whether it is available."""

    key: str
    nav_label: str
    title: str
    subtitle: str
    supported: bool
    platform: str
    unsupported_reason: str = ""
    #: Platform vocabulary the views substitute in (captions, empty states, prompts).
    terms: dict[str, str] = field(default_factory=dict)


def _has(tool: str) -> bool:
    return shutil.which(tool) is not None


def _current_platform() -> str:
    if is_windows():
        return "windows"
    if is_linux():
        return "linux"
    return "unsupported"


# --- Per-platform definitions -------------------------------------------------
#
# `available` is a callable so tool detection happens at call time rather than at
# import time, which keeps the registry testable.

_DEFINITIONS: dict[str, dict[str, dict[str, Any]]] = {
    STARTUP: {
        "windows": {
            "nav_label": "Startup Apps",
            "title": "Startup Applications",
            "subtitle": (
                "Inspect, enable, disable, and configure applications that launch "
                "automatically when Windows starts."
            ),
            "available": lambda: True,
            "terms": {
                "location_noun": "registry key or Startup folder",
                "os_name": "Windows",
                "add_hint": "Add a program or script to run at sign-in.",
            },
        },
        "linux": {
            "nav_label": "Startup Apps",
            "title": "Startup Applications",
            "subtitle": (
                "Inspect, enable, disable, and configure XDG autostart entries that "
                "launch automatically when your desktop session begins."
            ),
            "available": lambda: True,
            "terms": {
                "location_noun": "autostart directory",
                "os_name": "Linux",
                "add_hint": "Add a desktop entry to run at session start.",
            },
        },
    },
    SERVICES: {
        "windows": {
            "nav_label": "Services",
            "title": "Windows Services",
            "subtitle": (
                "Inspect background system and third-party services, start, stop, "
                "restart, and configure startup modes."
            ),
            "available": lambda: True,
            "terms": {
                "unit_noun": "service",
                "unit_noun_plural": "services",
                "console_label": "Open services.msc",
                "os_name": "Windows",
            },
        },
        "linux": {
            "nav_label": "Services",
            "title": "systemd Services",
            "subtitle": (
                "Inspect system and user systemd units, start, stop, restart, and "
                "configure whether they are enabled at boot."
            ),
            "available": lambda: _has("systemctl"),
            "terms": {
                "unit_noun": "unit",
                "unit_noun_plural": "units",
                "console_label": "Open systemd Manager",
                "os_name": "Linux",
            },
        },
    },
    SYSTEM_UPDATES: {
        "windows": {
            "nav_label": "System Updates",
            "title": "Windows Updates",
            "subtitle": (
                "Check for available system and security updates, initiate "
                "installations, and audit recent hotfix history."
            ),
            "available": lambda: True,
            "terms": {
                "update_noun": "update",
                "history_noun": "hotfix",
                "history_label": "Recently Installed Hotfixes",
                "settings_label": "Open Windows Update Settings",
                "os_name": "Windows",
            },
        },
        "linux": {
            "nav_label": "System Updates",
            "title": "System Updates",
            "subtitle": (
                "Check for distribution, kernel, and security updates from your "
                "system package manager, and review recent package history."
            ),
            "available": lambda: bool(
                _has("apt-get") or _has("dnf") or _has("yum") or _has("pacman") or _has("zypper")
            ),
            "terms": {
                "update_noun": "package update",
                "history_noun": "package transaction",
                "history_label": "Recent Package History",
                "settings_label": "Open Update Manager",
                "os_name": "Linux",
            },
        },
    },
    APP_UPDATES: {
        "windows": {
            "nav_label": "App Updates",
            "title": "App Updates",
            "subtitle": "Scan for available application updates via installed package managers.",
            "available": lambda: True,
            "terms": {"os_name": "Windows"},
        },
        "linux": {
            "nav_label": "App Updates",
            "title": "App Updates",
            "subtitle": "Scan for available application updates via installed package managers.",
            "available": lambda: True,
            "terms": {"os_name": "Linux"},
        },
    },
}

# Wording used when the running platform has no implementation at all.
_UNSUPPORTED_TEXT = {
    STARTUP: "Startup application management is not available on this operating system.",
    SERVICES: "Service management is not available on this operating system.",
    SYSTEM_UPDATES: "System update management is not available on this operating system.",
    APP_UPDATES: "No supported package manager was found on this operating system.",
}

# Wording used when the platform is supported in principle but its tooling is absent.
_MISSING_TOOL_TEXT = {
    (SERVICES, "linux"): "systemd was not detected (systemctl is not on PATH).",
    (
        SYSTEM_UPDATES,
        "linux",
    ): "No supported system package manager was found (apt, dnf, pacman, or zypper).",
}


def get_capability(key: str) -> Capability:
    """Describe one capability as it exists on the running platform."""
    platform = _current_platform()
    definition = _DEFINITIONS.get(key, {}).get(platform)

    if definition is None:
        return Capability(
            key=key,
            nav_label=key.replace("_", " ").title(),
            title=key.replace("_", " ").title(),
            subtitle="",
            supported=False,
            platform=platform,
            unsupported_reason=_UNSUPPORTED_TEXT.get(
                key, "This feature is not available on this operating system."
            ),
        )

    probe: Callable[[], bool] = definition["available"]
    available = bool(probe())
    reason = (
        "" if available else _MISSING_TOOL_TEXT.get((key, platform), _UNSUPPORTED_TEXT.get(key, ""))
    )

    return Capability(
        key=key,
        nav_label=definition["nav_label"],
        title=definition["title"],
        subtitle=definition["subtitle"],
        supported=available,
        platform=platform,
        unsupported_reason=reason,
        terms=dict(definition.get("terms", {})),
    )


def is_supported(key: str) -> bool:
    """Whether the running platform provides this capability."""
    return get_capability(key).supported


def term(key: str, name: str, default: str = "") -> str:
    """One piece of platform vocabulary for a capability, for use in UI strings."""
    return get_capability(key).terms.get(name, default)


def supported_capabilities() -> list[Capability]:
    """Every capability the running platform provides, in registry order."""
    return [cap for cap in (get_capability(k) for k in _DEFINITIONS) if cap.supported]


def capability_summary() -> dict[str, dict[str, Any]]:
    """Serialisable capability map, for `--json` output and diagnostics."""
    summary: dict[str, dict[str, Any]] = {}
    for key in _DEFINITIONS:
        cap = get_capability(key)
        summary[key] = {
            "label": cap.nav_label,
            "title": cap.title,
            "supported": cap.supported,
            "platform": cap.platform,
            "reason": cap.unsupported_reason,
        }
    return summary
