"""Windows Update - compatibility surface over the platform-neutral dispatcher.

The implementation moved to :mod:`crapcleaner.system.backends.updates_windows`, and
the platform-neutral entry points live in :mod:`crapcleaner.system.system_updates`.
This module keeps the original Windows-flavoured names working for existing callers.

New code should import from :mod:`crapcleaner.system.system_updates` instead, so it
works unchanged on Linux.
"""

from crapcleaner.system.capabilities import SYSTEM_UPDATES, get_capability
from crapcleaner.system.system_updates import (
    SystemUpdateItem,
    SystemUpdateReport,
    check_system_updates,
    ensure_update_service_running,
    install_system_updates,
    open_update_settings,
)

# The shared model is the same object under its historic names.
WindowsUpdateItem = SystemUpdateItem
WindowsUpdateReport = SystemUpdateReport

__all__ = [
    "WindowsUpdateItem",
    "WindowsUpdateReport",
    "check_windows_updates",
    "install_windows_updates",
    "open_windows_update_settings",
    "ensure_windows_update_service_running",
]


def check_windows_updates(
    include_history: bool = True, timeout: float = 30.0
) -> SystemUpdateReport:
    """Deprecated alias for :func:`crapcleaner.system.system_updates.check_system_updates`."""
    return check_system_updates(include_history=include_history, timeout=timeout)


def install_windows_updates(update_ids: list[str] | None = None) -> tuple[bool, str]:
    """Deprecated alias for :func:`crapcleaner.system.system_updates.install_system_updates`."""
    return install_system_updates(update_ids)


def open_windows_update_settings() -> bool:
    """Deprecated alias returning only the success flag, as the original did."""
    ok, _msg = open_update_settings()
    return ok


def ensure_windows_update_service_running() -> tuple[bool, str]:
    """Deprecated alias for :func:`ensure_update_service_running`."""
    if get_capability(SYSTEM_UPDATES).platform != "windows":
        return False, "Not running on Windows."
    return ensure_update_service_running()
