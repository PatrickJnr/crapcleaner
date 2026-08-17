"""System introspection and management.

Hardware specs, disk health, memory, startup entries, services, and updates.

The startup, services, and update managers are platform-neutral dispatchers: they
expose one API, consult :mod:`crapcleaner.system.capabilities` to find out what the
running operating system supports, and route to a backend in
:mod:`crapcleaner.system.backends`. Callers never branch on the platform themselves.
"""

from crapcleaner.system.capabilities import (
    APP_UPDATES,
    SERVICES,
    STARTUP,
    SYSTEM_UPDATES,
    Capability,
    capability_summary,
    get_capability,
    is_supported,
    supported_capabilities,
)
from crapcleaner.system.services import (
    ServiceItem,
    get_services_report,
    open_services_console,
    restart_service,
    set_service_startup_type,
    start_service,
    startup_types,
    stop_service,
)
from crapcleaner.system.startup import (
    StartupItem,
    add_scopes,
    add_startup_item,
    get_startup_items,
    remove_startup_item,
    set_startup_item_enabled,
)
from crapcleaner.system.system_updates import (
    SystemUpdateItem,
    SystemUpdateReport,
    check_system_updates,
    ensure_update_service_running,
    install_system_updates,
    open_update_settings,
)

# Historic Windows-flavoured names, kept so existing callers keep working.
WindowsUpdateItem = SystemUpdateItem
WindowsUpdateReport = SystemUpdateReport
check_windows_updates = check_system_updates
install_windows_updates = install_system_updates

__all__ = [
    # Capability registry
    "Capability",
    "STARTUP",
    "SERVICES",
    "SYSTEM_UPDATES",
    "APP_UPDATES",
    "get_capability",
    "is_supported",
    "supported_capabilities",
    "capability_summary",
    # Startup
    "StartupItem",
    "get_startup_items",
    "set_startup_item_enabled",
    "remove_startup_item",
    "add_startup_item",
    "add_scopes",
    # Services
    "ServiceItem",
    "get_services_report",
    "start_service",
    "stop_service",
    "restart_service",
    "set_service_startup_type",
    "startup_types",
    "open_services_console",
    # System updates
    "SystemUpdateItem",
    "SystemUpdateReport",
    "check_system_updates",
    "install_system_updates",
    "open_update_settings",
    "ensure_update_service_running",
    # Deprecated aliases
    "WindowsUpdateItem",
    "WindowsUpdateReport",
    "check_windows_updates",
    "install_windows_updates",
]
