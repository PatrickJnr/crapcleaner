"""Centralized filesystem safety layer and protected paths enforcement.

Enforces explicit rules preventing cleanup routines or analyzers from touching
system operating system folders, user documents, source code repositories,
credentials, keys, or application save state. Also enforces user-defined exclusions.
"""

import os
import threading
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


# The protected root list and the user's exclusion rules are the same for every path
# in a scan, but building them costs a resolve() syscall per entry. Rebuilding them
# per file made validate_cleanup_path dominate scan time, so both are cached and
# invalidated explicitly by refresh_protection_cache().
_cache_lock = threading.Lock()
_roots_cache: list[tuple[str, str]] | None = None
_exclusions_cache: tuple[tuple[str, ...], tuple[tuple[str, str], ...]] | None = None
#: Exclusions read from settings, cached separately so the default path never has to
#: touch config.json to discover its own cache key.
_settings_exclusions_cache: tuple[tuple[str, str], ...] | None = None


def refresh_protection_cache() -> None:
    """Drop the cached protected roots and exclusion rules.

    Called when settings change and at the start of a scan, so a newly mounted drive
    or an edited exclusion list is picked up.
    """
    global _roots_cache, _exclusions_cache, _settings_exclusions_cache
    with _cache_lock:
        _roots_cache = None
        _exclusions_cache = None
        _settings_exclusions_cache = None


def invalidate_settings_exclusions() -> None:
    """Force the next check to re-read the user's exclusion list from settings.

    Called once at the start of each directory scan, so edits made in Preferences take
    effect on the next scan without paying a config read per candidate file.
    """
    global _settings_exclusions_cache
    with _cache_lock:
        _settings_exclusions_cache = None


def _normalize_rules(exclusions) -> tuple[tuple[str, str], ...]:
    return tuple((norm, raw) for raw in exclusions if raw for norm in (_norm(raw),) if norm)


def _normalized_exclusions(exclusions: list[str] | None) -> tuple[tuple[str, str], ...]:
    """Normalise exclusion rules once, returning (normalised, original) pairs."""
    global _exclusions_cache, _settings_exclusions_cache

    if exclusions is None:
        with _cache_lock:
            cached = _settings_exclusions_cache
        if cached is not None:
            return cached
        try:
            from crapcleaner.config import load_settings

            from_settings = load_settings().get("excluded_paths", [])
        except Exception:
            from_settings = []
        normalized = _normalize_rules(from_settings)
        with _cache_lock:
            _settings_exclusions_cache = normalized
        return normalized

    key = tuple(exclusions)
    with _cache_lock:
        cached_exclusions = _exclusions_cache
    if cached_exclusions is not None and cached_exclusions[0] == key:
        return cached_exclusions[1]

    normalized = _normalize_rules(exclusions)
    with _cache_lock:
        _exclusions_cache = (key, normalized)
    return normalized


def get_protected_system_roots() -> list[tuple[str, str]]:
    """Return explicit system root directories and their protection reasons."""
    global _roots_cache
    with _cache_lock:
        cached = _roots_cache
    if cached is not None:
        return list(cached)

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

    resolved = [(p, reason) for p, reason in roots if p]
    with _cache_lock:
        _roots_cache = resolved
    return list(resolved)


def is_path_protected(path: str) -> bool:
    """Return True if the specified path matches a protected filesystem rule."""
    return explain_protection(path) is not None


def _is_excluded_norm(norm_target: str, exclusions: list[str] | None = None) -> tuple[bool, str]:
    """Exclusion check against an already-normalised target path."""
    if not norm_target:
        return False, ""

    for norm_excl, raw in _normalized_exclusions(exclusions):
        # Exact match, or the target sits underneath an excluded folder.
        if (
            norm_target == norm_excl
            or norm_target.startswith(norm_excl + "\\")
            or norm_target.startswith(norm_excl + "/")
        ):
            return True, f"User-defined exclusion rule: {raw}"

    return False, ""


def is_path_excluded(path: str, exclusions: list[str] | None = None) -> tuple[bool, str]:
    """Check if the given path matches any user-configured exclusion rules."""
    if not path:
        return False, ""
    return _is_excluded_norm(_norm(path), exclusions)


def explain_protection(path: str) -> str | None:
    """Return the safety rationale if the path is protected, otherwise None."""
    if not path:
        return "Path is empty"

    norm_target = _norm(path)
    if not norm_target:
        return "Invalid path"
    return _explain_protection_norm(norm_target)


def _explain_protection_norm(norm_target: str) -> str | None:
    """Protection rules applied to an already-normalised path."""
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


_BROWSER_PROFILE_PARTS = frozenset({"google", "chrome", "edge", "brave", "firefox"})
_BROWSER_CREDENTIAL_FILES = frozenset(
    {"login data", "cookies", "key4.db", "logins.json", "places.sqlite", "bookmarks"}
)


class DirectoryGuard:
    """Protection checks for the files of one directory, resolved once.

    Resolving every candidate path individually costs a `_getfinalpathname` syscall per
    file, which dominated scan time. Every rule except the filename ones depends only on
    the directory, so the directory is normalised once and each file is then checked
    lexically against that result.

    This is only sound where the caller guarantees the entries are not symbolic links,
    which the traversal in :mod:`crapcleaner.core.size` does by skipping them. Anything
    that deletes must still call :func:`validate_cleanup_path`, which resolves the exact
    path it is about to act on.
    """

    __slots__ = ("_ok", "_reason", "_norm_dir", "_parts", "_is_browser_profile", "_exclusions")

    def __init__(self, directory: str, exclusions: list[str] | None = None):
        self._norm_dir = _norm(directory)
        self._exclusions = _normalized_exclusions(exclusions)
        self._parts: tuple[str, ...] = ()
        self._is_browser_profile = False
        self._ok = True
        self._reason = ""

        if not self._norm_dir:
            self._ok, self._reason = False, "Invalid path"
            return

        self._evaluate(tuple(part.lower() for part in Path(self._norm_dir).parts))

    def child(self, name: str) -> "DirectoryGuard":
        """Guard for a subdirectory, derived without touching the filesystem.

        Resolving each directory costs a `_getfinalpathname` syscall, which on a deep
        tree runs an order of magnitude slower than on a shallow one and dominated scan
        time. The parent is already resolved and the traversal only descends through
        entries that are not symbolic links, so the child's real path is the parent's
        path with the name appended - no syscall required.
        """
        lowered = name.lower()
        derived = DirectoryGuard.__new__(DirectoryGuard)
        derived._exclusions = self._exclusions
        derived._norm_dir = f"{self._norm_dir}{os.sep}{lowered}"
        derived._ok = True
        derived._reason = ""
        derived._parts = ()
        derived._is_browser_profile = False

        if not self._ok:
            # A blocked directory blocks everything beneath it.
            derived._ok, derived._reason = False, self._reason
            derived._parts = self._parts + (lowered,)
            return derived

        derived._evaluate(self._parts + (lowered,))
        return derived

    def _evaluate(self, parts: tuple[str, ...]) -> None:
        self._parts = parts
        self._is_browser_profile = bool(_BROWSER_PROFILE_PARTS.intersection(parts))

        # Deliberately NOT the exact-root-match rule. That rule exists to stop the root
        # itself being deleted; a file inside %LOCALAPPDATA% is not the root, and real
        # cleanup categories scan directly inside protected roots. Applying it here
        # would silently return zero results for those categories.
        for d_name in _PROTECTED_DIR_NAMES:
            if d_name in parts:
                self._ok = False
                self._reason = f"Contains protected directory component: {d_name}"
                return
        if ".ssh" in parts or ".gnupg" in parts:
            self._ok, self._reason = False, "SSH or GPG encryption key storage"
            return

        for norm_excl, raw in self._exclusions:
            if (
                self._norm_dir == norm_excl
                or self._norm_dir.startswith(norm_excl + "\\")
                or self._norm_dir.startswith(norm_excl + "/")
            ):
                self._ok = False
                self._reason = f"Excluded: User-defined exclusion rule: {raw}"
                return

    @property
    def directory_allowed(self) -> bool:
        """Whether the directory itself may be traversed at all."""
        return self._ok

    @property
    def reason(self) -> str:
        return self._reason

    def allows_file(self, name: str) -> bool:
        """Whether a file directly inside this directory is safe to consider."""
        if not self._ok:
            return False

        lowered = name.lower()
        if lowered in _PROTECTED_FILENAMES or lowered in _PROTECTED_DIR_NAMES:
            return False
        if self._is_browser_profile and lowered in _BROWSER_CREDENTIAL_FILES:
            return False

        if self._exclusions:
            # The directory is already resolved, so joining is safe without a syscall.
            target = f"{self._norm_dir}{os.sep}{lowered}"
            for norm_excl, _raw in self._exclusions:
                if (
                    target == norm_excl
                    or target.startswith(norm_excl + "\\")
                    or target.startswith(norm_excl + "/")
                ):
                    return False
        return True


def validate_cleanup_path(path: str, exclusions: list[str] | None = None) -> tuple[bool, str]:
    """Validate whether a path is safe for cleanup. Returns (is_safe, message).

    Called once per candidate file during a scan, so the path is normalised a single
    time and shared by both checks rather than resolved twice.
    """
    if not path:
        return False, "Protected path blocked: Path is empty"

    norm_target = _norm(path)
    if not norm_target:
        return False, "Protected path blocked: Invalid path"

    # 1. Check system protection rules
    reason = _explain_protection_norm(norm_target)
    if reason:
        return False, f"Protected path blocked: {reason}"

    # 2. Check user exclusion rules
    is_excl, excl_reason = _is_excluded_norm(norm_target, exclusions)
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
