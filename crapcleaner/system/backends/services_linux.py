"""Linux service control, backed by systemd's ``systemctl``.

Covers both the system manager and the calling user's session manager. System units
need root, so writes are routed through ``pkexec`` (or an already-root process) and
refused with a clear message when no elevation path exists. User units never need
elevation and are always driven directly.
"""

import os
import shutil
from typing import TYPE_CHECKING

from crapcleaner.utils.platform import run_command

if TYPE_CHECKING:  # pragma: no cover - typing only
    from crapcleaner.system.services import ServiceItem

# Units that keep the running session alive. Stopping or masking any of these strands
# the desktop, the login session, or the ability to elevate at all.
CRITICAL_UNITS = {
    "systemd-journald",
    "systemd-logind",
    "systemd-udevd",
    "systemd-resolved",
    "dbus",
    "dbus-broker",
    "polkit",
    "systemd-oomd",
    "systemd-networkd",
    "networkmanager",
    "init",
    # Templated units: stopping user@1000 tears down the whole session, and getty
    # owns the console you would need to recover from that.
    "user",
    "getty",
    "serial-getty",
}

#: Unit -> "system" | "user", learned while listing so later actions target the right
#: manager. ponytail: a listing pass primes this; actions on an unlisted unit assume
#: the system manager. Query `systemctl --user cat` per action if that ever bites.
_UNIT_SCOPES: dict[str, str] = {}

#: Startup types this platform accepts, in the wording its UI uses.
STARTUP_TYPES = ("Automatic", "Manual", "Disabled")

# systemd unit-file states mapped onto the shared startup-type vocabulary.
_STATE_TO_STARTUP = {
    "enabled": "Automatic",
    "enabled-runtime": "Automatic",
    "alias": "Automatic",
    "disabled": "Manual",
    "indirect": "Manual",
    "static": "Static",
    "generated": "Static",
    "transient": "Static",
    "masked": "Disabled",
    "masked-runtime": "Disabled",
    "bad": "Unknown",
    "not-found": "Unknown",
}


def is_critical(name: str) -> bool:
    unit = name.lower().strip().removesuffix(".service")
    if unit in CRITICAL_UNITS:
        return True
    # getty@tty1, user@1000 and friends - the template is what matters.
    return unit.split("@", 1)[0] in CRITICAL_UNITS


def _unit_id(name: str) -> str:
    """Full systemd unit id for a display name."""
    stripped = name.strip()
    return stripped if "." in stripped.rsplit("/", 1)[-1] else f"{stripped}.service"


def _systemctl(args: list[str], scope: str = "system", timeout: float = 15.0):
    base = ["systemctl"] + (["--user"] if scope == "user" else [])
    return run_command(base + args + ["--no-pager"], timeout=timeout)


def _read_unit_file_states(scope: str) -> dict[str, str]:
    """Map unit id -> unit-file state (enabled, disabled, masked, static, ...)."""
    res = _systemctl(
        ["list-unit-files", "--type=service", "--no-legend", "--plain"],
        scope=scope,
        timeout=15.0,
    )
    states: dict[str, str] = {}
    for line in str(res.get("stdout", "")).splitlines():
        parts = line.split()
        if len(parts) >= 2:
            states[parts[0]] = parts[1].lower()
    return states


def _list_scope(scope: str) -> list["ServiceItem"]:
    from crapcleaner.system.services import ServiceItem

    res = _systemctl(
        ["list-units", "--type=service", "--all", "--no-legend", "--plain"],
        scope=scope,
        timeout=15.0,
    )
    stdout = str(res.get("stdout", "")).strip()
    if not stdout:
        return []

    file_states = _read_unit_file_states(scope)
    account = "root" if scope == "system" else (os.environ.get("USER") or "user")
    items: list[ServiceItem] = []

    for line in stdout.splitlines():
        # UNIT LOAD ACTIVE SUB DESCRIPTION - the description is the only field that
        # may contain spaces, so it takes the remainder.
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        unit, _load, active_state, sub_state = parts[0], parts[1], parts[2], parts[3]
        description = parts[4].strip() if len(parts) > 4 else ""

        if not unit.endswith(".service"):
            continue

        name = unit.removesuffix(".service")
        _UNIT_SCOPES[name] = scope

        if active_state == "active":
            status = "Running" if sub_state == "running" else "Pending" if "start" in sub_state else "Running"
        elif active_state == "activating" or active_state == "deactivating":
            status = "Pending"
        elif active_state == "failed":
            status = "Failed"
        else:
            status = "Stopped"

        startup_type = _STATE_TO_STARTUP.get(file_states.get(unit, ""), "Unknown")
        critical = is_critical(name)

        items.append(
            ServiceItem(
                name=name,
                display_name=description or name,
                status=status,
                startup_type=startup_type,
                description=description,
                account=account,
                # ponytail: skipping MainPID keeps this to two subprocess calls for the
                # whole listing. Add a `systemctl show` pass if the PID is ever needed.
                pid=None,
                is_system=scope == "system",
                can_stop=not critical,
                scope=scope,
            )
        )
    return items


def list_services() -> list["ServiceItem"]:
    services = _list_scope("system")
    # A user manager only exists inside a session; its absence is normal, not an error.
    services.extend(_list_scope("user"))
    return services


def _scope_for(name: str) -> str:
    return _UNIT_SCOPES.get(name.removesuffix(".service"), "system")


def _privileged(args: list[str], scope: str, timeout: float = 20.0):
    """Run a mutating systemctl command, elevating for system units when needed."""
    if scope == "user" or os.geteuid() == 0:
        return _systemctl(args, scope=scope, timeout=timeout)

    if shutil.which("pkexec"):
        return run_command(["pkexec", "systemctl"] + args + ["--no-pager"], timeout=timeout)

    if shutil.which("sudo"):
        # -n so a password prompt cannot block the GUI; it fails fast instead.
        return run_command(["sudo", "-n", "systemctl"] + args + ["--no-pager"], timeout=timeout)

    return {
        "returncode": -1,
        "stdout": "",
        "stderr": "no elevation helper",
        "error": "no elevation helper",
    }


def _explain(res, action: str, name: str) -> str:
    stderr = str(res.get("stderr") or "").strip()
    if res.get("error") == "no elevation helper":
        return (
            f"Root privileges are required to {action} the system unit '{name}', and neither "
            "pkexec nor sudo is available. Run CrapCleaner as root, or install polkit."
        )
    if "authentication" in stderr.lower() or "not authorized" in stderr.lower():
        return f"Authorisation to {action} '{name}' was declined."
    if "not found" in stderr.lower() or "not loaded" in stderr.lower():
        return f"Unit '{name}' was not found."
    return f"Failed to {action} '{name}': {stderr or 'systemctl reported an error'}"


def _run_action(verb: str, name: str, past: str) -> tuple[bool, str]:
    scope = _scope_for(name)
    res = _privileged([verb, _unit_id(name)], scope=scope)
    if res.get("returncode") == 0:
        suffix = " (user session)" if scope == "user" else ""
        return True, f"Unit '{name}' {past}{suffix}."
    return False, _explain(res, verb, name)


def start(name: str) -> tuple[bool, str]:
    return _run_action("start", name, "started")


def stop(name: str) -> tuple[bool, str]:
    return _run_action("stop", name, "stopped")


def restart(name: str) -> tuple[bool, str]:
    return _run_action("restart", name, "restarted")


def normalize_startup_type(startup_type: str) -> tuple[str, str]:
    """Map a free-form startup type onto (display name, systemctl verb).

    ``Disabled`` masks the unit, which is what actually prevents it from being started
    by anything; ``systemctl disable`` alone only removes it from boot.
    """
    st = startup_type.strip().lower()
    if "disable" in st or "mask" in st:
        return "Disabled", "mask"
    if "manual" in st or "demand" in st:
        return "Manual", "disable"
    return "Automatic", "enable"


def set_startup_type(name: str, startup_type: str) -> tuple[bool, str]:
    target_type, verb = normalize_startup_type(startup_type)
    scope = _scope_for(name)
    unit = _unit_id(name)

    # Leaving the Disabled state means lifting the mask first; enable/disable are
    # rejected outright by systemd while a unit is masked.
    if verb != "mask":
        _privileged(["unmask", unit], scope=scope)

    res = _privileged([verb, unit], scope=scope)
    if res.get("returncode") == 0:
        return True, f"Startup for unit '{name}' set to {target_type}."
    return False, _explain(res, f"set startup for", name)


def open_console() -> tuple[bool, str]:
    """systemd has no bundled GUI console; point at the equivalent command instead."""
    for candidate in ("systemadm", "systemd-ui"):
        if shutil.which(candidate):
            run_command([candidate], timeout=5.0)
            return True, f"Opened {candidate}."
    return False, "No systemd GUI is installed. Use `systemctl status <unit>` in a terminal."
