"""Service Manager - platform-neutral dispatcher.

Holds the shared :class:`ServiceItem` model, the result cache, and the safety rules
that apply on every platform, then routes each operation to the backend for the
running operating system:

* Windows -> :mod:`crapcleaner.system.backends.services_windows` (CIM/PowerShell, sc.exe)
* Linux   -> :mod:`crapcleaner.system.backends.services_linux` (systemd via systemctl)

Callers never branch on the platform themselves. When the running system has no
service manager, every entry point returns a refusal carrying the reason from
:mod:`crapcleaner.system.capabilities` instead of letting a platform command fail.
"""

import threading
import time
from dataclasses import dataclass
from typing import Any

from crapcleaner.system.capabilities import SERVICES, get_capability

_SERVICES_CACHE_TTL = 30.0
_cache_lock = threading.Lock()
_cached_services: tuple[float, list["ServiceItem"]] | None = None


@dataclass
class ServiceItem:
    """One background service, described identically on every platform."""

    name: str
    display_name: str
    status: str  # Running, Stopped, Paused, Pending, Failed, Unknown
    startup_type: str  # Automatic, Automatic (Delayed Start), Manual, Disabled, Static, Unknown
    description: str
    account: str
    pid: int | None
    is_system: bool
    can_stop: bool = True
    can_pause: bool = False
    #: "system" for the machine-wide manager, "user" for the session manager (Linux).
    scope: str = "system"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "status": self.status,
            "startup_type": self.startup_type,
            "description": self.description,
            "account": self.account,
            "pid": self.pid,
            "is_system": self.is_system,
            "can_stop": self.can_stop,
            "can_pause": self.can_pause,
            "scope": self.scope,
        }


def _backend():
    """The service backend for the running platform, or None when unsupported."""
    cap = get_capability(SERVICES)
    if not cap.supported:
        return None
    if cap.platform == "windows":
        from crapcleaner.system.backends import services_windows

        return services_windows
    from crapcleaner.system.backends import services_linux

    return services_linux


def _unsupported() -> str:
    return get_capability(SERVICES).unsupported_reason or "Service management is unavailable."


def is_available() -> bool:
    """Whether this platform can manage services at all."""
    return _backend() is not None


def startup_types() -> tuple[str, ...]:
    """Startup types this platform accepts, for populating UI menus."""
    backend = _backend()
    return backend.STARTUP_TYPES if backend else ()


def is_critical_service(name: str) -> bool:
    """Whether losing this service would destabilise the running system."""
    backend = _backend()
    return bool(backend and backend.is_critical(name))


def get_services_report(force_refresh: bool = False) -> list[ServiceItem]:
    """Inspect and return every service the platform reports."""
    global _cached_services
    now = time.monotonic()

    if not force_refresh:
        with _cache_lock:
            cached = _cached_services
        if cached is not None and now - cached[0] < _SERVICES_CACHE_TTL:
            return list(cached[1])

    backend = _backend()
    services: list[ServiceItem] = []
    if backend is not None:
        try:
            services = backend.list_services()
        except Exception:
            services = []

    services.sort(key=lambda s: (s.status != "Running", s.display_name.lower()))

    with _cache_lock:
        _cached_services = (time.monotonic(), services)

    return list(services)


def clear_services_cache() -> None:
    global _cached_services
    with _cache_lock:
        _cached_services = None


def _prepare(name: str) -> tuple[str, tuple[bool, str] | None]:
    """Validate a service name and confirm the platform can act on it."""
    clean = name.strip()
    if not clean:
        return clean, (False, "Service name cannot be empty.")
    if _backend() is None:
        return clean, (False, _unsupported())
    return clean, None


def start_service(name: str) -> tuple[bool, str]:
    clean, refusal = _prepare(name)
    if refusal:
        return refusal
    clear_services_cache()
    return _backend().start(clean)


def stop_service(name: str, force: bool = False) -> tuple[bool, str]:
    clean, refusal = _prepare(name)
    if refusal:
        return refusal
    if is_critical_service(clean) and not force:
        os_name = get_capability(SERVICES).terms.get("os_name", "system")
        return False, f"Service '{clean}' is a critical {os_name} component and cannot be stopped."
    clear_services_cache()
    return _backend().stop(clean)


def restart_service(name: str) -> tuple[bool, str]:
    clean, refusal = _prepare(name)
    if refusal:
        return refusal
    clear_services_cache()
    return _backend().restart(clean)


def set_service_startup_type(name: str, startup_type: str) -> tuple[bool, str]:
    clean, refusal = _prepare(name)
    if refusal:
        return refusal

    backend = _backend()
    target_type, _ = backend.normalize_startup_type(startup_type)
    if is_critical_service(clean) and target_type == "Disabled":
        os_name = get_capability(SERVICES).terms.get("os_name", "system")
        return False, f"Service '{clean}' is a critical {os_name} component and cannot be disabled."

    clear_services_cache()
    return backend.set_startup_type(clean, startup_type)


def open_services_console() -> tuple[bool, str]:
    """Open the platform's own service management console, when it has one."""
    backend = _backend()
    if backend is None:
        return False, _unsupported()
    return backend.open_console()


def open_services_msc() -> bool:
    """Backwards-compatible alias for the Windows services console."""
    ok, _ = open_services_console()
    return ok
