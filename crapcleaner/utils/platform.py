"""Cross-platform helpers for paths, storage, and process execution."""

import ctypes
import os
import shutil
import subprocess
import sys
from pathlib import Path


def expand_env(path: str) -> str:
    return os.path.expandvars(os.path.expanduser(path))


def resolve_paths(paths: list[str]) -> list[str]:
    out = []
    for p in paths:
        resolved = expand_env(p)
        if resolved:
            out.append(resolved)
    return out


def get_drive_info(drive: str = "C:") -> dict[str, int | str]:
    if is_windows():
        target = f"{drive}\\" if not drive.endswith(("\\", "/")) else drive
        total, used, free = shutil.disk_usage(target)
        return {"total": total, "used": used, "free": free}

    target = drive if drive and drive != "C:" else "/"
    total, used, free = shutil.disk_usage(target)
    mount_meta = get_mount_metadata().get(target, {})
    return {
        "total": total,
        "used": used,
        "free": free,
        "label": mount_meta.get("source", ""),
        "filesystem": mount_meta.get("filesystem", ""),
    }


def get_mount_metadata() -> dict[str, dict[str, str]]:
    metadata: dict[str, dict[str, str]] = {}
    if is_windows():
        return metadata
    try:
        with open("/proc/mounts", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 3:
                    continue
                source = parts[0].replace("\\040", " ")
                mount_point = parts[1].replace("\\040", " ")
                fs_type = parts[2]
                metadata[mount_point] = {"source": source, "filesystem": fs_type}
    except OSError:
        pass
    return metadata


def _is_visible_linux_mount(mount_point: str, fs_type: str) -> bool:
    if fs_type in {
        "proc",
        "sysfs",
        "tmpfs",
        "devtmpfs",
        "devpts",
        "cgroup",
        "cgroup2",
        "overlay",
        "squashfs",
        "nsfs",
        "tracefs",
        "debugfs",
        "securityfs",
        "pstore",
        "autofs",
        "mqueue",
        "hugetlbfs",
        "rpc_pipefs",
        "fusectl",
        "efivarfs",
        "bpf",
        "configfs",
        "selinuxfs",
        "binfmt_misc",
    }:
        return False
    if mount_point.startswith("/run/"):
        return False
    if mount_point.startswith("/home/") and "/.git" in mount_point:
        return False
    if mount_point.startswith("/home/") and "/CrapCleaner/" in mount_point:
        return False
    return True


def _linux_mount_sort_key(mount_point: str) -> tuple[int, int, str]:
    priority = 0 if mount_point == "/" else 1
    return (priority, len(mount_point), mount_point)


def _dedupe_linux_mounts(mounts: list[str], metadata: dict[str, dict[str, str]]) -> list[str]:
    deduped: list[str] = []
    seen_signatures: set[tuple[str, str, int, int, int]] = set()

    for mount_point in sorted(mounts, key=_linux_mount_sort_key):
        info = metadata.get(mount_point, {})
        source = info.get("source", "")
        fs_type = info.get("filesystem", "")
        try:
            usage = shutil.disk_usage(mount_point)
        except OSError:
            deduped.append(mount_point)
            continue

        signature = (source, fs_type, usage.total, usage.used, usage.free)
        if source and signature in seen_signatures:
            continue

        deduped.append(mount_point)
        if source:
            seen_signatures.add(signature)

    return deduped


def list_drives() -> list[str]:
    """Return mounted filesystem roots for the current platform."""
    if is_windows():
        try:
            mask = ctypes.windll.kernel32.GetLogicalDrives()
            letters = [chr(65 + i) for i in range(26) if mask >> i & 1]
        except Exception:  # pragma: no cover - defensive
            letters = []

        if not letters:
            try:
                buf = ctypes.create_unicode_buffer(256)
                ctypes.windll.kernel32.GetLogicalDriveStringsW(256, buf)
                letters = [r.rstrip("\\") for r in buf.value.split("\x00") if r]
            except Exception:  # pragma: no cover - defensive
                letters = []

        return [f"{letter}:\\" for letter in letters] or ["C:\\"]

    mounts: list[str] = []
    metadata = get_mount_metadata()
    try:
        for mount_point, info in metadata.items():
            fs_type = info.get("filesystem", "")
            if not _is_visible_linux_mount(mount_point, fs_type):
                continue
            if mount_point not in mounts:
                mounts.append(mount_point)
    except OSError:
        mounts = ["/"]

    return _dedupe_linux_mounts(mounts, metadata) or ["/"]


def is_admin() -> bool:
    if not sys.platform.startswith("win"):
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevate() -> bool:
    if is_admin():
        return True
    if not sys.platform.startswith("win"):
        return False
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, _elevation_args(), None, 1
        )
        return True
    except Exception:
        return False


def _elevation_args() -> str:
    if getattr(sys, "frozen", False):
        return " ".join(f'"{a}"' for a in sys.argv[1:])
    script = Path(sys.argv[0]).resolve()
    args = [f'"{script}"'] + [f'"{a}"' for a in sys.argv[1:]]
    return " ".join(args)


def relaunch_as_admin(argv: list[str] | None = None) -> bool:
    if is_admin():
        return True
    if not sys.platform.startswith("win"):
        return False
    argv = argv or sys.argv
    params = " ".join(f'"{a}"' for a in argv[1:])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", argv[0], params, None, 1)
    return True


def is_windows() -> bool:
    return sys.platform.startswith("win")


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def get_user_profile() -> str:
    return os.environ.get("USERPROFILE", os.path.expanduser("~"))


def get_local_appdata() -> str:
    if is_windows():
        return os.environ.get("LOCALAPPDATA", "")
    return os.environ.get("XDG_CACHE_HOME", os.path.join(get_user_profile(), ".cache"))


def get_appdata() -> str:
    if is_windows():
        return os.environ.get("APPDATA", "")
    return os.environ.get("XDG_CONFIG_HOME", os.path.join(get_user_profile(), ".config"))


def get_program_data() -> str:
    if is_windows():
        return os.environ.get("PROGRAMDATA", "C:\\ProgramData")
    return "/var/cache"


def get_program_files_x86() -> str:
    if is_windows():
        return os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
    return "/usr/local"


def get_windows_dir() -> str:
    if is_windows():
        return os.environ.get("SystemRoot", "C:\\Windows")
    return "/"


def which(program: str) -> str | None:
    for base in os.environ.get("PATH", "").split(os.pathsep):
        candidate = os.path.join(base, program)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
        if os.path.isfile(candidate + ".exe"):
            return candidate + ".exe"
    return None


def run_command(
    args: list[str],
    timeout: float = 120.0,
    cwd: str | None = None,
) -> dict[str, object]:
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            creationflags=(subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0),
        )
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "error": None,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "returncode": -1,
            "stdout": exc.stdout or "",
            "stderr": "timed out",
            "error": "timed out",
        }
    except FileNotFoundError as exc:
        return {"returncode": -2, "stdout": "", "stderr": str(exc), "error": str(exc)}


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)
