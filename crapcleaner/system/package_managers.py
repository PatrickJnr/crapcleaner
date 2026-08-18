"""Package Manager integration for CrapCleaner.

Detects available package managers on the current OS and provides
cross-platform support for listing available updates and installing them.

Supported managers:
  Windows: winget, chocolatey (choco)
  Linux:   apt/apt-get, flatpak, snap, pacman, dnf/yum
"""

import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from crapcleaner.utils.platform import is_linux, is_windows

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class PackageUpdate:
    id: str
    name: str
    current_version: str
    available_version: str
    manager: str
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "current_version": self.current_version,
            "available_version": self.available_version,
            "manager": self.manager,
            "source": self.source,
        }


@dataclass
class ManagerResult:
    manager: str
    updates: list = field(default_factory=list)
    error: str = ""
    available: bool = True


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_CACHE_TTL = 120.0

# Installers are killed when they exceed these. Large packages (IDEs, SDKs, Adobe)
# routinely run for many minutes, and a half-installed package is worse than a slow
# one, so these are generous rather than snappy.
_INSTALL_TIMEOUT = 1800.0
_INSTALL_ALL_TIMEOUT = 7200.0
_cache_lock = threading.Lock()
_cached = None


def _clear_cache() -> None:
    global _cached
    with _cache_lock:
        _cached = None


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------


def _cmd_exists(name: str) -> bool:
    return shutil.which(name) is not None


def detect_managers() -> list:
    available = []
    if is_windows():
        if _cmd_exists("winget"):
            available.append("winget")
        if _cmd_exists("choco"):
            available.append("choco")
    elif is_linux():
        if _cmd_exists("apt"):
            available.append("apt")
        elif _cmd_exists("apt-get"):
            available.append("apt-get")
        if _cmd_exists("flatpak"):
            available.append("flatpak")
        if _cmd_exists("snap"):
            available.append("snap")
        if _cmd_exists("pacman"):
            available.append("pacman")
        if _cmd_exists("dnf"):
            available.append("dnf")
        elif _cmd_exists("yum"):
            available.append("yum")
    return available


# ---------------------------------------------------------------------------
# Subprocess helper
# ---------------------------------------------------------------------------


def _run(args, timeout=60.0, env_extra=None):
    import os

    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=env)
        return result.returncode, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except FileNotFoundError:
        return -1, "", f"Command not found: {args[0]}"
    except Exception as exc:
        return -1, "", str(exc)


# ---------------------------------------------------------------------------
# Winget
# ---------------------------------------------------------------------------

# No "" entry here: str.startswith("") is always True and would skip every row.
_WINGET_SKIP_PREFIXES = ("Name", "-", "\\", "The following", "upgrades available", "No applicable")


def _column_bounds(header):
    """(start, end) slice bounds for each column of a winget table header."""
    starts = [m.start() for m in re.finditer(r"\S+", header)]
    if len(starts) < 4:
        return None
    return list(zip(starts, starts[1:] + [None]))


def _parse_winget_upgrades(text):
    updates = []
    lines = text.splitlines()
    bounds = None
    for index, line in enumerate(lines):
        stripped = line.rstrip()
        if re.match(r"^[-\s]+$", stripped) and len(stripped) > 5:
            # Separator row: the line above it holds the column offsets.
            bounds = _column_bounds(lines[index - 1]) if index else None
            continue
        if bounds is None or not stripped:
            continue
        if any(stripped.startswith(p) for p in _WINGET_SKIP_PREFIXES):
            continue
        # winget pads cells to a fixed width, so a value that fills its column is
        # separated from the next by a single space - splitting on runs of spaces
        # would merge the two. Slice by header offsets, and only fall back to the
        # space split when the offsets clearly do not line up with this row.
        cols = [line[start:end].strip() for start, end in bounds]
        if not cols[1] or re.search(r"\s", cols[1]):
            cols = [col.strip() for col in re.split(r"\s{2,}", stripped)]
        if len(cols) < 4:
            continue
        name, pkg_id, current, available = cols[0], cols[1], cols[2], cols[3]
        source = cols[4] if len(cols) > 4 else ""
        if not pkg_id or not available:
            continue
        updates.append(
            PackageUpdate(
                id=pkg_id,
                name=name or pkg_id,
                current_version=current,
                available_version=available,
                manager="winget",
                source=source,
            )
        )
    return updates


def _get_winget_updates():
    result = ManagerResult(manager="winget")
    rc, stdout, stderr = _run(
        ["winget", "upgrade", "--accept-source-agreements", "--disable-interactivity"], timeout=60.0
    )
    if rc == -1 and "not found" in stderr:
        result.available = False
        result.error = "winget not found"
        return result
    result.updates = _parse_winget_upgrades(stdout)
    return result


# ---------------------------------------------------------------------------
# Chocolatey
# ---------------------------------------------------------------------------


def _parse_choco_outdated(text):
    updates = []
    for line in text.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        parts = line.split("|")
        if len(parts) < 3:
            continue
        pkg_id, current, available = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if not pkg_id or not available:
            continue
        updates.append(
            PackageUpdate(
                id=pkg_id,
                name=pkg_id,
                current_version=current,
                available_version=available,
                manager="choco",
                source="chocolatey.org",
            )
        )
    return updates


def _get_choco_updates():
    result = ManagerResult(manager="choco")
    rc, stdout, stderr = _run(["choco", "outdated", "--limit-output", "--no-color"], timeout=60.0)
    if rc == -1 and "not found" in stderr:
        result.available = False
        result.error = "choco not found"
        return result
    result.updates = _parse_choco_outdated(stdout)
    return result


# ---------------------------------------------------------------------------
# APT
# ---------------------------------------------------------------------------


def _get_apt_updates(manager="apt"):
    result = ManagerResult(manager=manager)
    _run(["sudo", "-n", manager, "-q", "update"], timeout=30.0)
    rc, stdout, stderr = _run(
        [manager, "list", "--upgradable", "--quiet"],
        timeout=30.0,
        env_extra={"DEBIAN_FRONTEND": "noninteractive"},
    )
    if rc == -1 and "not found" in stderr:
        result.available = False
        result.error = f"{manager} not found"
        return result
    for line in stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("Listing...") or line.startswith("WARNING"):
            continue
        m = re.match(r"^(\S+)/(\S+)\s+(\S+)\s+\S+.*upgradable from:\s+(\S+)", line)
        if m:
            name_arch, source, available, current = (
                m.group(1),
                m.group(2),
                m.group(3),
                m.group(4).rstrip(")"),
            )
            pkg_id = name_arch.split(":")[0]
            result.updates.append(
                PackageUpdate(
                    id=pkg_id,
                    name=pkg_id,
                    current_version=current,
                    available_version=available,
                    manager=manager,
                    source=source,
                )
            )
    return result


# ---------------------------------------------------------------------------
# Flatpak
# ---------------------------------------------------------------------------


def _get_flatpak_updates():
    result = ManagerResult(manager="flatpak")
    rc, stdout, stderr = _run(
        ["flatpak", "remote-ls", "--updates", "--columns=application,name,version,branch"],
        timeout=30.0,
    )
    if rc == -1 and "not found" in stderr:
        result.available = False
        result.error = "flatpak not found"
        return result
    for line in stdout.splitlines():
        cols = line.strip().split("\t")
        if len(cols) < 2:
            cols = re.split(r"\s{2,}", line.strip())
        if len(cols) < 2:
            continue
        app_id = cols[0].strip()
        name = cols[1].strip() if len(cols) > 1 else app_id
        available = cols[2].strip() if len(cols) > 2 else "update available"
        branch = cols[3].strip() if len(cols) > 3 else ""
        if not app_id:
            continue
        result.updates.append(
            PackageUpdate(
                id=app_id,
                name=name or app_id,
                current_version="",
                available_version=available or branch or "update available",
                manager="flatpak",
                source="flathub",
            )
        )
    return result


# ---------------------------------------------------------------------------
# Snap
# ---------------------------------------------------------------------------


def _get_snap_updates():
    result = ManagerResult(manager="snap")
    rc, stdout, stderr = _run(["snap", "refresh", "--list"], timeout=20.0)
    if rc == -1 and "not found" in stderr:
        result.available = False
        result.error = "snap not found"
        return result
    lines = stdout.splitlines()
    past_header = False
    for line in lines:
        stripped = line.strip()
        if not past_header:
            if re.match(r"^Name\s+Version", stripped):
                past_header = True
            continue
        if not stripped:
            continue
        cols = re.split(r"\s{2,}", stripped)
        if len(cols) < 2:
            continue
        name, available = cols[0].strip(), cols[1].strip()
        result.updates.append(
            PackageUpdate(
                id=name,
                name=name,
                current_version="",
                available_version=available,
                manager="snap",
                source="snapcraft.io",
            )
        )
    return result


# ---------------------------------------------------------------------------
# Pacman
# ---------------------------------------------------------------------------


def _get_pacman_updates():
    result = ManagerResult(manager="pacman")
    if _cmd_exists("checkupdates"):
        rc, stdout, stderr = _run(["checkupdates"], timeout=30.0)
    else:
        rc, stdout, stderr = _run(["pacman", "-Qu"], timeout=30.0)
    if rc == -1 and "not found" in stderr:
        result.available = False
        result.error = "pacman not found"
        return result
    for line in stdout.splitlines():
        m = re.match(r"^(\S+)\s+(\S+)\s+->\s+(\S+)", line.strip())
        if m:
            result.updates.append(
                PackageUpdate(
                    id=m.group(1),
                    name=m.group(1),
                    current_version=m.group(2),
                    available_version=m.group(3),
                    manager="pacman",
                    source="pacman",
                )
            )
    return result


# ---------------------------------------------------------------------------
# DNF/YUM
# ---------------------------------------------------------------------------


def _get_dnf_updates(manager="dnf"):
    result = ManagerResult(manager=manager)
    rc, stdout, stderr = _run([manager, "check-update", "--quiet"], timeout=60.0)
    if rc == -1 and "not found" in stderr:
        result.available = False
        result.error = f"{manager} not found"
        return result
    for line in stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("Last metadata") or line.startswith("Obsoleting"):
            continue
        parts = re.split(r"\s+", line)
        if len(parts) < 3:
            continue
        name_arch, available, source = parts[0], parts[1], parts[2] if len(parts) > 2 else ""
        pkg_id = name_arch.rsplit(".", 1)[0]
        result.updates.append(
            PackageUpdate(
                id=pkg_id,
                name=pkg_id,
                current_version="",
                available_version=available,
                manager=manager,
                source=source,
            )
        )
    return result


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------


def get_all_updates(force_refresh=False):
    global _cached
    now = time.monotonic()
    if not force_refresh:
        with _cache_lock:
            cached = _cached
        if cached is not None and now - cached[0] < _CACHE_TTL:
            return list(cached[1])

    managers = detect_managers()
    results = []
    for mgr in managers:
        try:
            if mgr == "winget":
                results.append(_get_winget_updates())
            elif mgr == "choco":
                results.append(_get_choco_updates())
            elif mgr in ("apt", "apt-get"):
                results.append(_get_apt_updates(mgr))
            elif mgr == "flatpak":
                results.append(_get_flatpak_updates())
            elif mgr == "snap":
                results.append(_get_snap_updates())
            elif mgr == "pacman":
                results.append(_get_pacman_updates())
            elif mgr in ("dnf", "yum"):
                results.append(_get_dnf_updates(mgr))
        except Exception as exc:
            results.append(ManagerResult(manager=mgr, error=str(exc)))

    with _cache_lock:
        _cached = (time.monotonic(), results)
    return results


def install_update(manager, pkg_id):
    _clear_cache()
    try:
        if manager == "winget":
            rc, stdout, stderr = _run(
                [
                    "winget",
                    "upgrade",
                    "--id",
                    pkg_id,
                    "--exact",
                    "--silent",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                    "--disable-interactivity",
                ],
                timeout=_INSTALL_TIMEOUT,
            )
        elif manager == "choco":
            rc, stdout, stderr = _run(
                ["choco", "upgrade", pkg_id, "-y", "--no-progress"], timeout=_INSTALL_TIMEOUT
            )
        elif manager in ("apt", "apt-get"):
            rc, stdout, stderr = _run(
                ["sudo", "-n", manager, "install", "--only-upgrade", "-y", pkg_id],
                timeout=_INSTALL_TIMEOUT,
                env_extra={"DEBIAN_FRONTEND": "noninteractive"},
            )
        elif manager == "flatpak":
            rc, stdout, stderr = _run(["flatpak", "update", "-y", pkg_id], timeout=_INSTALL_TIMEOUT)
        elif manager == "snap":
            rc, stdout, stderr = _run(["snap", "refresh", pkg_id], timeout=_INSTALL_TIMEOUT)
        elif manager == "pacman":
            rc, stdout, stderr = _run(
                ["pacman", "-S", "--noconfirm", pkg_id], timeout=_INSTALL_TIMEOUT
            )
        elif manager in ("dnf", "yum"):
            rc, stdout, stderr = _run([manager, "upgrade", "-y", pkg_id], timeout=_INSTALL_TIMEOUT)
        else:
            return False, f"Unsupported package manager: {manager}"
        ok = rc == 0
        return ok, stdout.strip() or (
            "Updated successfully." if ok else stderr.strip() or "Update failed."
        )
    except Exception as exc:
        return False, str(exc)


def install_all_updates(manager):
    _clear_cache()
    try:
        if manager == "winget":
            rc, stdout, stderr = _run(
                [
                    "winget",
                    "upgrade",
                    "--all",
                    "--silent",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ],
                timeout=_INSTALL_ALL_TIMEOUT,
            )
        elif manager == "choco":
            rc, stdout, stderr = _run(
                ["choco", "upgrade", "all", "-y", "--no-progress"], timeout=_INSTALL_ALL_TIMEOUT
            )
        elif manager in ("apt", "apt-get"):
            rc, stdout, stderr = _run(
                ["sudo", "-n", manager, "upgrade", "-y"],
                timeout=_INSTALL_ALL_TIMEOUT,
                env_extra={"DEBIAN_FRONTEND": "noninteractive"},
            )
        elif manager == "flatpak":
            rc, stdout, stderr = _run(["flatpak", "update", "-y"], timeout=_INSTALL_ALL_TIMEOUT)
        elif manager == "snap":
            rc, stdout, stderr = _run(["snap", "refresh"], timeout=_INSTALL_ALL_TIMEOUT)
        elif manager == "pacman":
            rc, stdout, stderr = _run(
                ["pacman", "-Syu", "--noconfirm"], timeout=_INSTALL_ALL_TIMEOUT
            )
        elif manager in ("dnf", "yum"):
            rc, stdout, stderr = _run([manager, "upgrade", "-y"], timeout=_INSTALL_ALL_TIMEOUT)
        else:
            return False, f"Unsupported package manager: {manager}"
        ok = rc == 0
        return ok, stdout.strip() or (
            "All packages updated." if ok else stderr.strip() or "Update failed."
        )
    except Exception as exc:
        return False, str(exc)
