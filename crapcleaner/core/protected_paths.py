"""Centralized filesystem safety layer and protected paths enforcement.

Enforces explicit rules preventing cleanup routines or analyzers from touching
system operating system folders, user documents, source code repositories,
credentials, keys, or application save state. Also enforces user-defined exclusions.
"""

import os
from pathlib import Path

from crapcleaner.utils.platform import (
    get_appdata,
    get_local_appdata,
    get_program_data,
    get_user_profile,
    get_windows_dir,
    is_windows,
    list_drives,
)

_PROTECTED_FILENAMES = frozenset(
    {
        "id_rsa",
        "id_rsa.pub",
        "id_ed25519",
        "id_ed25519.pub",
        "id_ecdsa",
        "id_ecdsa.pub",
        "id_dsa",
        "id_dsa.pub",
        "known_hosts",
        "authorized_keys",
        "login data",
        "login data for account",
        "cookies",
        "cookies-journal",
        "key4.db",
        "logins.json",
        "places.sqlite",
        "bookmarks",
        "preferences",
        "web data",
        "ntuser.dat",
        "usrclass.dat",
        "sam",
        "system",
        "security",
        "software",
    }
)

_PROTECTED_DIR_NAMES = frozenset(
    {
        ".git",
        ".ssh",
        ".gnupg",
        ".aws",
        ".azure",
        ".kube",
        "system volume information",
        "$recycle.bin",
    }
)


def _norm(path: str) -> str:
    if not path:
        return ""
    try:
        resolved = str(Path(os.path.expandvars(os.path.expanduser(path))).resolve())
        return resolved.lower().rstrip("\\/")
    except (OSError, ValueError):
        return path.lower().replace("/", "\\").rstrip("\\/")


def get_protected_system_roots() -> list[tuple[str, str]]:
    """Return explicit system root directories and their protection reasons."""
    roots: list[tuple[str, str]] = []

    # Drive roots
    for drive in list_drives():
        norm_drive = _norm(drive)
        if norm_drive:
            roots.append((norm_drive, f"Filesystem volume root ({drive})"))

    if is_windows():
        windir = _norm(get_windows_dir())
        if windir:
            roots.append((windir, "Operating system directory (Windows)"))
            roots.append(
                (_norm(os.path.join(windir, "System32")), "Critical Windows system binaries")
            )
            roots.append(
                (_norm(os.path.join(windir, "SysWOW64")), "Windows 32-bit subsystem binaries")
            )

        prog_data = _norm(get_program_data())
        if prog_data:
            roots.append((prog_data, "System ProgramData directory root"))

        user = _norm(get_user_profile())
        if user:
            roots.append((user, "User profile root directory"))
            roots.append((_norm(os.path.join(user, "Documents")), "User Documents directory"))
            roots.append((_norm(os.path.join(user, "Desktop")), "User Desktop directory"))
            roots.append((_norm(os.path.join(user, "Pictures")), "User Pictures directory"))
            roots.append((_norm(os.path.join(user, "Music")), "User Music directory"))
            roots.append((_norm(os.path.join(user, "Videos")), "User Videos directory"))
            roots.append((_norm(os.path.join(user, "Saved Games")), "User Saved Games directory"))
            roots.append(
                (
                    _norm(os.path.join(user, "AppData", "LocalLow")),
                    "Application save and config root",
                )
            )

        appdata = _norm(get_appdata())
        if appdata:
            roots.append((appdata, "Roaming AppData root"))

        local = _norm(get_local_appdata())
        if local:
            roots.append((local, "Local AppData root"))

    else:  # Linux / Unix
        linux_system_roots = [
            ("/", "Root filesystem"),
            ("/bin", "System binaries"),
            ("/sbin", "System administration binaries"),
            ("/usr", "User system hierarchy"),
            ("/usr/bin", "User binaries"),
            ("/usr/lib", "System libraries"),
            ("/etc", "System configuration files"),
            ("/boot", "Boot loader and kernel files"),
            ("/dev", "Device nodes"),
            ("/proc", "Process information pseudo-filesystem"),
            ("/sys", "Kernel sysfs pseudo-filesystem"),
            ("/root", "Root user home directory"),
            ("/var/log", "System log directory root"),
        ]
        for p, desc in linux_system_roots:
            roots.append((_norm(p), desc))

        user = _norm(get_user_profile())
        if user:
            roots.append((user, "User home directory"))
            roots.append((_norm(os.path.join(user, "Documents")), "User Documents directory"))
            roots.append((_norm(os.path.join(user, "Desktop")), "User Desktop directory"))
            roots.append((_norm(os.path.join(user, "Pictures")), "User Pictures directory"))
            roots.append((_norm(os.path.join(user, "Music")), "User Music directory"))
            roots.append((_norm(os.path.join(user, "Videos")), "User Videos directory"))

    return [(p, reason) for p, reason in roots if p]


def is_path_protected(path: str) -> bool:
    """Return True if the specified path matches a protected filesystem rule."""
    return explain_protection(path) is not None


def is_path_excluded(path: str, exclusions: list[str] | None = None) -> tuple[bool, str]:
    """Check if the given path matches any user-configured exclusion rules."""
    if not path:
        return False, ""
    norm_target = _norm(path)
    if not norm_target:
        return False, ""

    if exclusions is None:
        try:
            from crapcleaner.config import load_settings

            exclusions = load_settings().get("excluded_paths", [])
        except Exception:
            exclusions = []

    for excl in exclusions:
        if not excl:
            continue
        norm_excl = _norm(excl)
        if not norm_excl:
            continue
        # Exact match or subpath of excluded folder
        if (
            norm_target == norm_excl
            or norm_target.startswith(norm_excl + "\\")
            or norm_target.startswith(norm_excl + "/")
        ):
            return True, f"User-defined exclusion rule: {excl}"

    return False, ""


def explain_protection(path: str) -> str | None:
    """Return the safety rationale if the path is protected, otherwise None."""
    if not path:
        return "Path is empty"

    norm_target = _norm(path)
    if not norm_target:
        return "Invalid path"

    # 1. Direct match with protected system/user roots
    for root_path, reason in get_protected_system_roots():
        if norm_target == root_path:
            return f"Exact match with protected root: {reason}"

    # 2. Check protected filename patterns
    base_name = os.path.basename(norm_target).lower()
    if base_name in _PROTECTED_FILENAMES:
        return f"Protected critical file or credential: {base_name}"

    # 3. Check protected path components / directory names (.git, .ssh, etc.)
    parts = [part.lower() for part in Path(norm_target).parts]
    for d_name in _PROTECTED_DIR_NAMES:
        if d_name in parts:
            return f"Contains protected directory component: {d_name}"

    # 4. Check browser credential signatures (e.g. within Chromium/Firefox profiles)
    if (
        "google" in parts
        or "chrome" in parts
        or "edge" in parts
        or "brave" in parts
        or "firefox" in parts
    ) and (
        base_name
        in ("login data", "cookies", "key4.db", "logins.json", "places.sqlite", "bookmarks")
    ):
        return "Browser credential database or bookmark file"

    # 5. Check SSH / GPG private keys
    if ".ssh" in parts or ".gnupg" in parts:
        return "SSH or GPG encryption key storage"

    return None


def validate_cleanup_path(path: str, exclusions: list[str] | None = None) -> tuple[bool, str]:
    """Validate whether a path is safe for cleanup. Returns (is_safe, message)."""
    # 1. Check system protection rules
    reason = explain_protection(path)
    if reason:
        return False, f"Protected path blocked: {reason}"

    # 2. Check user exclusion rules
    is_excl, excl_reason = is_path_excluded(path, exclusions=exclusions)
    if is_excl:
        return False, f"Excluded path skipped: {excl_reason}"

    return True, "Path is allowed for cleanup analysis"


def get_protected_rules_summary() -> list[dict[str, str]]:
    """Return a structured summary of all active protection rules."""
    summary = []
    for path, reason in get_protected_system_roots():
        summary.append({"rule_type": "Protected Root", "target": path, "reason": reason})
    summary.append(
        {
            "rule_type": "Protected Directory Pattern",
            "target": ", ".join(sorted(_PROTECTED_DIR_NAMES)),
            "reason": "Git repositories, SSH keys, GPG keys, and system metadata folders",
        }
    )
    summary.append(
        {
            "rule_type": "Protected File Pattern",
            "target": ", ".join(sorted(_PROTECTED_FILENAMES)),
            "reason": "Passwords, credentials, cookies, bookmarks, and system registry hives",
        }
    )
    return summary
