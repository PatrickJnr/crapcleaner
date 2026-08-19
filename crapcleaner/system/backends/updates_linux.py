"""Linux distribution updates via the system package manager.

Covers apt, dnf/yum, pacman, and zypper. Checks are read-only and run unprivileged;
installation needs root and is routed through ``pkexec``/``sudo -n``, refusing with an
explanation when neither is present rather than dropping a password prompt behind the
GUI.

This is the distribution-level counterpart to Windows Update: kernels, security
errata, and system packages. Per-application upgrades live in
:mod:`crapcleaner.system.package_managers`.
"""

import os
import re
import shutil
from typing import TYPE_CHECKING

from crapcleaner.utils.platform import run_command

if TYPE_CHECKING:  # pragma: no cover - typing only
    from crapcleaner.system.system_updates import SystemUpdateReport

#: Managers in probe order; the first one present owns the system.
_MANAGERS = ("apt-get", "dnf", "yum", "pacman", "zypper")

# Files whose presence means the running kernel or core libraries are stale.
_REBOOT_MARKERS = ("/var/run/reboot-required", "/run/reboot-required")


def detect_manager() -> str:
    for manager in _MANAGERS:
        if shutil.which(manager):
            return manager
    return ""


def service_status() -> str:
    manager = detect_manager()
    return f"{manager} available" if manager else "No package manager detected"


def _reboot_required(manager: str) -> bool:
    if any(os.path.exists(marker) for marker in _REBOOT_MARKERS):
        return True
    if manager in ("dnf", "yum") and shutil.which("needs-restarting"):
        # Exit code 1 means a reboot is needed; 0 means it is not.
        res = run_command(["needs-restarting", "-r"], timeout=10.0)
        return res.get("returncode") == 1
    return False


def _severity_for(source: str, name: str) -> str:
    haystack = f"{source} {name}".lower()
    if "security" in haystack:
        return "Critical"
    if "kernel" in haystack or "linux-image" in haystack:
        return "Important"
    return "Moderate"


# --- Available update collection ---------------------------------------------


def _check_apt() -> list[tuple[str, str, str, str]]:
    """Return (package, current, available, source) rows from apt."""
    res = run_command(
        ["apt-get", "--just-print", "upgrade"],
        timeout=30.0,
    )
    rows: list[tuple[str, str, str, str]] = []
    # "Inst linux-image-generic [6.8.0-31] (6.8.0-40 Ubuntu:24.04/noble-security [amd64])"
    pattern = re.compile(r"^Inst\s+(\S+)\s+\[([^\]]*)\]\s+\(([^\s)]+)\s+([^)]*)\)")
    for line in str(res.get("stdout", "")).splitlines():
        match = pattern.match(line.strip())
        if match:
            rows.append((match.group(1), match.group(2), match.group(3), match.group(4).strip()))
    return rows


def _check_dnf(manager: str) -> list[tuple[str, str, str, str]]:
    res = run_command([manager, "check-update", "--quiet"], timeout=60.0)
    security = _dnf_security_packages(manager)
    rows: list[tuple[str, str, str, str]] = []
    for line in str(res.get("stdout", "")).splitlines():
        line = line.strip()
        if not line or line.startswith(("Last metadata", "Obsoleting", "Security:")):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        name = parts[0].rsplit(".", 1)[0]
        source = parts[2]
        if name in security:
            source = f"{source} security"
        rows.append((name, "", parts[1], source))
    return rows


def _dnf_security_packages(manager: str) -> set[str]:
    res = run_command([manager, "check-update", "--security", "--quiet"], timeout=60.0)
    names: set[str] = set()
    for line in str(res.get("stdout", "")).splitlines():
        parts = line.strip().split()
        if len(parts) >= 3:
            names.add(parts[0].rsplit(".", 1)[0])
    return names


def _check_pacman() -> list[tuple[str, str, str, str]]:
    # checkupdates queries a private database copy, so it needs no root.
    command = ["checkupdates"] if shutil.which("checkupdates") else ["pacman", "-Qu"]
    res = run_command(command, timeout=30.0)
    rows: list[tuple[str, str, str, str]] = []
    for line in str(res.get("stdout", "")).splitlines():
        match = re.match(r"^(\S+)\s+(\S+)\s+->\s+(\S+)", line.strip())
        if match:
            rows.append((match.group(1), match.group(2), match.group(3), "pacman"))
    return rows


def _check_zypper() -> list[tuple[str, str, str, str]]:
    res = run_command(["zypper", "--non-interactive", "list-updates"], timeout=60.0)
    rows: list[tuple[str, str, str, str]] = []
    for line in str(res.get("stdout", "")).splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 5 and parts[0] == "v":
            rows.append((parts[2], parts[3], parts[4], parts[1]))
    return rows


_CHECKERS = {
    "apt-get": lambda _m: _check_apt(),
    "dnf": _check_dnf,
    "yum": _check_dnf,
    "pacman": lambda _m: _check_pacman(),
    "zypper": lambda _m: _check_zypper(),
}


# --- Installed history --------------------------------------------------------


def _history_apt(limit: int) -> list[tuple[str, str]]:
    """Return (summary, timestamp) rows from the apt history log."""
    entries: list[tuple[str, str]] = []
    log_path = "/var/log/apt/history.log"
    if not os.path.isfile(log_path):
        return entries
    try:
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            blocks = fh.read().split("\n\n")
    except OSError:
        return entries

    for block in reversed(blocks):
        if not block.strip():
            continue
        fields = dict(
            (line.split(":", 1)[0].strip(), line.split(":", 1)[1].strip())
            for line in block.splitlines()
            if ":" in line
        )
        summary = fields.get("Commandline") or fields.get("Upgrade") or fields.get("Install")
        if not summary:
            continue
        entries.append((summary[:200], fields.get("Start-Date", "")))
        if len(entries) >= limit:
            break
    return entries


def _history_dnf(manager: str, limit: int) -> list[tuple[str, str]]:
    res = run_command([manager, "history", "list", "--quiet"], timeout=20.0)
    entries: list[tuple[str, str]] = []
    for line in str(res.get("stdout", "")).splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3 and parts[0].isdigit():
            entries.append((f"Transaction {parts[0]}: {parts[1]}", parts[2]))
        if len(entries) >= limit:
            break
    return entries


def _history_pacman(limit: int) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    log_path = "/var/log/pacman.log"
    if not os.path.isfile(log_path):
        return entries
    try:
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError:
        return entries

    for line in reversed(lines):
        match = re.match(r"^\[([^\]]+)\]\s+\[ALPM\]\s+(upgraded|installed)\s+(.+)$", line.strip())
        if match:
            entries.append((f"{match.group(2)} {match.group(3)}", match.group(1)))
        if len(entries) >= limit:
            break
    return entries


def _collect_history(manager: str, limit: int = 25) -> list[tuple[str, str]]:
    if manager == "apt-get":
        return _history_apt(limit)
    if manager in ("dnf", "yum"):
        return _history_dnf(manager, limit)
    if manager == "pacman":
        return _history_pacman(limit)
    return []


# --- Public backend API -------------------------------------------------------


def check(include_history: bool = True, timeout: float = 30.0) -> "SystemUpdateReport":
    from crapcleaner.system.system_updates import SystemUpdateItem, SystemUpdateReport

    manager = detect_manager()
    report = SystemUpdateReport(backend=manager or "unknown", service_status=service_status())

    if not manager:
        report.error = "No supported system package manager was found."
        return report

    try:
        rows = _CHECKERS[manager](manager)
    except Exception as exc:
        report.error = f"Failed to query {manager} for updates: {exc}"
        return report

    for name, current, available, source in rows:
        severity = _severity_for(source, name)
        report.available_updates.append(
            SystemUpdateItem(
                id=name,
                title=f"{name} {available}" if available else name,
                kb_numbers=[],
                description=(f"{current} → {available}" if current else f"Update to {available}"),
                size_bytes=0,
                categories=[c for c in (source,) if c],
                severity=severity,
                is_downloaded=False,
                is_mandatory=severity == "Critical",
                support_url="",
                status="Available",
            )
        )

    if include_history:
        for summary, timestamp in _collect_history(manager):
            report.installed_history.append(
                SystemUpdateItem(
                    id=f"{manager}:{timestamp}:{summary[:40]}",
                    title=summary,
                    kb_numbers=[],
                    description=f"Recorded by {manager}",
                    size_bytes=0,
                    categories=[manager],
                    severity="Installed",
                    is_downloaded=True,
                    is_mandatory=False,
                    support_url="",
                    installed_on=timestamp,
                    status="Installed",
                )
            )

    report.reboot_required = _reboot_required(manager)
    return report


_INSTALL_COMMANDS = {
    "apt-get": ["apt-get", "-y", "-o", "Dpkg::Options::=--force-confdef", "upgrade"],
    "dnf": ["dnf", "-y", "upgrade"],
    "yum": ["yum", "-y", "upgrade"],
    "pacman": ["pacman", "-Syu", "--noconfirm"],
    "zypper": ["zypper", "--non-interactive", "update"],
}


def _elevated(command: list[str], timeout: float):
    if getattr(os, "geteuid", lambda: 1)() == 0:
        return run_command(command, timeout=timeout)
    if shutil.which("pkexec"):
        return run_command(["pkexec"] + command, timeout=timeout)
    if shutil.which("sudo"):
        return run_command(["sudo", "-n"] + command, timeout=timeout)
    return {
        "returncode": -1,
        "stdout": "",
        "stderr": "no elevation helper",
        "error": "no elevation helper",
    }


def install(update_ids: list[str] | None = None) -> tuple[bool, str]:
    manager = detect_manager()
    if not manager:
        return False, "No supported system package manager was found."

    command = list(_INSTALL_COMMANDS[manager])
    if update_ids:
        if manager == "pacman":
            command = ["pacman", "-S", "--noconfirm"] + list(update_ids)
        elif manager == "zypper":
            command = ["zypper", "--non-interactive", "update"] + list(update_ids)
        else:
            command = command + list(update_ids)

    # Distribution upgrades pull hundreds of packages; give them room to finish.
    res = _elevated(command, timeout=7200.0)

    if res.get("error") == "no elevation helper":
        return False, (
            "Root privileges are required to install system updates, and neither pkexec nor "
            "sudo is available. Run CrapCleaner as root, or install polkit."
        )

    if res.get("returncode") == 0:
        reboot = (
            " A reboot is required to finish applying these updates."
            if _reboot_required(manager)
            else ""
        )
        return True, f"System updates installed via {manager}.{reboot}"

    stderr = str(res.get("stderr") or res.get("stdout") or "").strip()
    if "authentication" in stderr.lower() or "not authorized" in stderr.lower():
        return False, "Authorisation to install system updates was declined."
    return False, f"Failed to install system updates via {manager}: {stderr or 'unknown error'}"


#: GUI update managers, in the order they are tried.
_UPDATE_GUIS = (
    "gnome-software",
    "plasma-discover",
    "mintupdate",
    "yast2",
    "pamac-manager",
)


def open_settings() -> tuple[bool, str]:
    for candidate in _UPDATE_GUIS:
        if shutil.which(candidate):
            run_command([candidate], timeout=5.0)
            return True, f"Opened {candidate}."
    manager = detect_manager() or "your package manager"
    return False, f"No graphical update manager is installed. Use `{manager}` from a terminal."


def ensure_service_running() -> tuple[bool, str]:
    """Package managers are invoked on demand; there is no daemon to start."""
    manager = detect_manager()
    if manager:
        return True, f"{manager} is available and runs on demand."
    return False, "No supported system package manager was found."
