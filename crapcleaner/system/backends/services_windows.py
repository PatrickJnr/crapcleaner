"""Windows service control, backed by CIM/PowerShell with an sc.exe fallback."""

import json
import subprocess
from typing import TYPE_CHECKING

from crapcleaner.utils.platform import is_admin, run_command
from crapcleaner.utils.windows_errors import explain_windows_error

if TYPE_CHECKING:  # pragma: no cover - typing only
    from crapcleaner.system.services import ServiceItem

# Services whose loss breaks the running session outright. Stopping or disabling any
# of these is refused rather than merely warned about.
CRITICAL_SERVICES = {
    "rpcss",
    "dcomlaunch",
    "lsm",
    "plugplay",
    "samss",
    "eventlog",
    "coremessagingregistrar",
    "schedule",
    "profsvc",
    "gpsvc",
    "brokerinfrastructure",
    "power",
    "cryptsvc",
    "dhcp",
    "dnscache",
    "winlogon",
}

_SYSTEM_ACCOUNTS = (
    "localsystem",
    "nt authority\\localservice",
    "nt authority\\networkservice",
)


def is_critical(name: str) -> bool:
    return name.lower().strip() in CRITICAL_SERVICES


def _parse_start_mode(start_mode: str, delayed: bool = False) -> str:
    sm = str(start_mode).strip().lower()
    if sm in ("auto", "automatic"):
        return "Automatic (Delayed Start)" if delayed else "Automatic"
    if sm in ("manual", "demand"):
        return "Manual"
    if sm == "disabled":
        return "Disabled"
    return start_mode.capitalize() if start_mode else "Unknown"


def _parse_state(state: str) -> str:
    st = str(state).strip().lower()
    if "run" in st:
        return "Running"
    if "stop" in st:
        return "Stopped"
    if "pause" in st:
        return "Paused"
    if "pend" in st:
        return "Pending"
    return state.capitalize() if state else "Unknown"


def list_services() -> list["ServiceItem"]:
    from crapcleaner.system.services import ServiceItem

    ps_cmd = (
        "try { "
        "Get-CimInstance Win32_Service | Select-Object -Property "
        "Name, DisplayName, State, StartMode, DelayedAutoStart, Description, StartName, ProcessId | "
        "ConvertTo-Json -Depth 2 -Compress "
        "} catch { "
        "Get-Service | Select-Object -Property Name, DisplayName, Status, StartType | "
        "ConvertTo-Json -Depth 2 -Compress "
        "}"
    )
    res = run_command(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
        timeout=15.0,
    )
    stdout = str(res.get("stdout", "")).strip()
    if not stdout:
        return []

    try:
        data = json.loads(stdout)
    except Exception:
        return []

    services: list[ServiceItem] = []
    for item in data if isinstance(data, list) else [data]:
        name = str(item.get("Name") or "")
        if not name:
            continue

        raw_state = item.get("State") or item.get("Status") or "Unknown"
        raw_start = item.get("StartMode") or item.get("StartType") or "Unknown"
        account = str(item.get("StartName") or "LocalSystem")
        pid_val = item.get("ProcessId")

        services.append(
            ServiceItem(
                name=name,
                display_name=str(item.get("DisplayName") or name),
                status=_parse_state(str(raw_state)),
                startup_type=_parse_start_mode(
                    str(raw_start), bool(item.get("DelayedAutoStart", False))
                ),
                description=str(item.get("Description") or ""),
                account=account,
                pid=int(pid_val) if pid_val and int(pid_val) > 0 else None,
                is_system=(
                    is_critical(name)
                    or account.lower() in _SYSTEM_ACCOUNTS
                    or name.lower().startswith(("win", "ms", "appx", "wua", "diag", "bfe"))
                ),
                can_stop=not is_critical(name),
                scope="system",
            )
        )
    return services


#: PowerShell reads the service name from the environment rather than from the command
#: text. Interpolating it - `-Name '{name}'` - lets a name containing an apostrophe end
#: the quoted string and append its own commands, which is the pattern this codebase
#: rejects everywhere else (see `utils.files.reveal_in_file_manager`). The value of an
#: environment variable is substituted as a single argument and is never re-parsed.
_PS_BASE = ["powershell", "-NoProfile", "-NonInteractive", "-Command"]
_NAME_VAR = "CRAPCLEANER_SERVICE_NAME"
_TYPE_VAR = "CRAPCLEANER_SERVICE_STARTUP"


def _run_service_command(script: str, name: str, timeout: float, startup_type: str = ""):
    """Run a service cmdlet with its arguments supplied through the environment."""
    env = {_NAME_VAR: name}
    if startup_type:
        env[_TYPE_VAR] = startup_type
    return run_command(_PS_BASE + [script], timeout=timeout, env_extra=env)


def _requires_admin(action: str, name: str) -> tuple[bool, str] | None:
    if is_admin():
        return None
    return False, f"Administrator elevation is required to {action} service '{name}'."


def start(name: str) -> tuple[bool, str]:
    denied = _requires_admin("start", name)
    if denied:
        return denied

    res = _run_service_command(
        f"Start-Service -Name $env:{_NAME_VAR} -ErrorAction Stop", name, timeout=20.0
    )
    if res.get("returncode") == 0:
        return True, f"Service '{name}' started successfully."

    fallback = run_command(["sc.exe", "start", name], timeout=10.0)
    if (
        fallback.get("returncode") == 0
        or "already running" in str(fallback.get("stdout", "")).lower()
    ):
        return True, f"Service '{name}' started successfully."

    err = str(res.get("stderr") or fallback.get("stderr") or "Access Denied").strip()
    return False, explain_windows_error(f"Failed to start service '{name}': {err}")


def stop(name: str) -> tuple[bool, str]:
    denied = _requires_admin("stop", name)
    if denied:
        return denied

    res = _run_service_command(
        f"Stop-Service -Name $env:{_NAME_VAR} -Force -ErrorAction Stop", name, timeout=20.0
    )
    if res.get("returncode") == 0:
        return True, f"Service '{name}' stopped successfully."

    fallback = run_command(["sc.exe", "stop", name], timeout=10.0)
    if fallback.get("returncode") == 0:
        return True, f"Service '{name}' stopped successfully."

    err = str(res.get("stderr") or fallback.get("stderr") or "Access Denied").strip()
    return False, explain_windows_error(f"Failed to stop service '{name}': {err}")


def restart(name: str) -> tuple[bool, str]:
    denied = _requires_admin("restart", name)
    if denied:
        return denied

    res = _run_service_command(
        f"Restart-Service -Name $env:{_NAME_VAR} -Force -ErrorAction Stop", name, timeout=30.0
    )
    if res.get("returncode") == 0:
        return True, f"Service '{name}' restarted successfully."

    err = str(res.get("stderr") or "Access Denied").strip()
    return False, explain_windows_error(f"Failed to restart service '{name}': {err}")


#: Startup types this platform accepts, in the wording its UI uses.
STARTUP_TYPES = ("Automatic", "Automatic (Delayed Start)", "Manual", "Disabled")


def normalize_startup_type(startup_type: str) -> tuple[str, str]:
    """Map a free-form startup type onto (display name, sc.exe start= value)."""
    st = startup_type.strip().lower()
    if "disable" in st:
        return "Disabled", "disabled"
    if "manual" in st or "demand" in st:
        return "Manual", "demand"
    if "delayed" in st:
        return "Automatic (Delayed Start)", "delayed-auto"
    return "Automatic", "auto"


def set_startup_type(name: str, startup_type: str) -> tuple[bool, str]:
    denied = _requires_admin("configure", name)
    if denied:
        return denied

    target_type, sc_start = normalize_startup_type(startup_type)
    # Set-Service does not accept the delayed variant as a StartupType value.
    ps_type = "Automatic" if target_type.startswith("Automatic") else target_type

    res = _run_service_command(
        f"Set-Service -Name $env:{_NAME_VAR} -StartupType $env:{_TYPE_VAR} -ErrorAction Stop",
        name,
        timeout=15.0,
        startup_type=ps_type,
    )
    if res.get("returncode") == 0 and sc_start != "delayed-auto":
        return True, f"Startup type for service '{name}' set to {target_type}."

    fallback = run_command(["sc.exe", "config", name, f"start= {sc_start}"], timeout=10.0)
    if fallback.get("returncode") == 0:
        return True, f"Startup type for service '{name}' set to {target_type}."

    err = str(res.get("stderr") or fallback.get("stderr") or "Access Denied").strip()
    return False, explain_windows_error(f"Failed to configure service '{name}': {err}")


def open_console() -> tuple[bool, str]:
    """Open the Windows Services management console."""
    try:
        subprocess.Popen(["services.msc"], shell=True)
        return True, "Opened the Windows Services console."
    except Exception as exc:
        return False, f"Could not open services.msc: {exc}"
