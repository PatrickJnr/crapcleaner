"""System Update Manager - platform-neutral dispatcher.

Holds the shared update model and routes each operation to the backend for the running
operating system:

* Windows -> :mod:`crapcleaner.system.backends.updates_windows` (Microsoft.Update COM)
* Linux   -> :mod:`crapcleaner.system.backends.updates_linux` (apt, dnf, pacman, zypper)

This covers operating-system updates: kernels, security fixes, and system packages.
Per-application upgrades are a separate concern handled by
:mod:`crapcleaner.system.package_managers`.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from crapcleaner.system.capabilities import SYSTEM_UPDATES, get_capability


@dataclass
class SystemUpdateItem:
    """One pending or installed system update, described identically per platform."""

    id: str
    title: str
    kb_numbers: list[str]
    description: str
    size_bytes: int
    categories: list[str]
    severity: str  # Critical, Important, Moderate, Low, Unspecified, Installed
    is_downloaded: bool
    is_mandatory: bool
    support_url: str
    installed_on: str | None = None
    status: str = "Available"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "kb_numbers": self.kb_numbers,
            "description": self.description,
            "size_bytes": self.size_bytes,
            "categories": self.categories,
            "severity": self.severity,
            "is_downloaded": self.is_downloaded,
            "is_mandatory": self.is_mandatory,
            "support_url": self.support_url,
            "installed_on": self.installed_on,
            "status": self.status,
        }


@dataclass
class SystemUpdateReport:
    """The result of one update check."""

    available_updates: list[SystemUpdateItem] = field(default_factory=list)
    installed_history: list[SystemUpdateItem] = field(default_factory=list)
    last_checked: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    service_status: str = "Unknown"
    error: str | None = None
    #: Which update system produced this report ("Windows Update", "apt-get", ...).
    backend: str = ""
    reboot_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "available_updates": [u.to_dict() for u in self.available_updates],
            "installed_history": [u.to_dict() for u in self.installed_history],
            "last_checked": self.last_checked,
            "service_status": self.service_status,
            "error": self.error,
            "backend": self.backend,
            "reboot_required": self.reboot_required,
        }


def _backend():
    """The update backend for the running platform, or None when unsupported."""
    cap = get_capability(SYSTEM_UPDATES)
    if not cap.supported:
        return None
    if cap.platform == "windows":
        from crapcleaner.system.backends import updates_windows

        return updates_windows
    from crapcleaner.system.backends import updates_linux

    return updates_linux


def _unsupported() -> str:
    return get_capability(SYSTEM_UPDATES).unsupported_reason or "System updates are unavailable."


def is_available() -> bool:
    """Whether this platform exposes system update management."""
    return _backend() is not None


def check_system_updates(include_history: bool = True, timeout: float = 30.0) -> SystemUpdateReport:
    """Search for pending system updates and, optionally, recent update history."""
    backend = _backend()
    if backend is None:
        return SystemUpdateReport(service_status="Not Applicable", error=_unsupported())
    try:
        return backend.check(include_history=include_history, timeout=timeout)
    except Exception as exc:
        return SystemUpdateReport(service_status="Unknown", error=f"Update check failed: {exc}")


def install_system_updates(update_ids: list[str] | None = None) -> tuple[bool, str]:
    """Download and install pending system updates."""
    backend = _backend()
    if backend is None:
        return False, _unsupported()
    return backend.install(update_ids)


def open_update_settings() -> tuple[bool, str]:
    """Open the platform's own update interface."""
    backend = _backend()
    if backend is None:
        return False, _unsupported()
    return backend.open_settings()


def ensure_update_service_running() -> tuple[bool, str]:
    """Make sure whatever the update check depends on is running."""
    backend = _backend()
    if backend is None:
        return False, _unsupported()
    return backend.ensure_service_running()
