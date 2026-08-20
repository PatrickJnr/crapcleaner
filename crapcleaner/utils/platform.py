"""Cross-platform helpers for paths, storage, and process execution."""

import ctypes
import os
import re
import shutil
import stat
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def expand_env(path: str) -> str:
    return os.path.expandvars(os.path.expanduser(path))


def resolve_paths(paths: list[str]) -> list[str]:
    out = []
    for p in paths:
        resolved = expand_env(p)
        if resolved:
            out.append(resolved)
    return out


def _windows_volume_info(root: str) -> tuple[str, str]:
    """(label, filesystem) for a Windows volume.

    An unlabelled drive, an empty card reader or a disconnected network drive
    reports "" rather than a placeholder.
    """
    label_buf = ctypes.create_unicode_buffer(261)
    fs_buf = ctypes.create_unicode_buffer(261)
    try:
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(root),
            label_buf,
            ctypes.sizeof(label_buf) // ctypes.sizeof(ctypes.c_wchar),
            None,
            None,
            None,
            fs_buf,
            ctypes.sizeof(fs_buf) // ctypes.sizeof(ctypes.c_wchar),
        )
    except (AttributeError, OSError):
        return "", ""
    if not ok:
        return "", ""
    return label_buf.value, fs_buf.value


def get_drive_info(drive: str = "C:") -> dict[str, int | str]:
    if is_windows():
        target = f"{drive}\\" if not drive.endswith(("\\", "/")) else drive
        total, used, free = shutil.disk_usage(target)
        label, filesystem = _windows_volume_info(target)
        # Same keys on both platforms; a per-platform shape pushed is_windows()
        # checks into the views.
        return {
            "total": total,
            "used": used,
            "free": free,
            "label": label,
            "filesystem": filesystem,
            "display_name": label or f"Drive {drive.rstrip(chr(92))}",
            "display_kind": "LOCAL",
        }

    target = drive if drive and drive != "C:" else "/"
    total, used, free = shutil.disk_usage(target)
    mount_meta = get_mount_metadata().get(target, {})
    return {
        "total": total,
        "used": used,
        "free": free,
        "label": mount_meta.get("source", ""),
        "filesystem": mount_meta.get("filesystem", ""),
        "display_name": linux_drive_display_name(target),
        "display_kind": linux_drive_display_kind(target),
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
        "ramfs",
    }:
        return False
    if mount_point in {"/proc", "/sys", "/dev", "/run", "/boot", "/boot/efi"}:
        return False
    if mount_point.startswith(("/proc/", "/sys/", "/dev/", "/run/")):
        return False
    if mount_point.startswith("/var/lib/docker/") or mount_point.startswith("/var/lib/containers/"):
        return False
    if mount_point.startswith("/home/") and "/.git" in mount_point:
        return False
    if mount_point.startswith("/home/") and "/CrapCleaner/" in mount_point:
        return False

    if mount_point == "/":
        return True

    allowed_prefixes = (
        "/home",
        "/mnt",
        "/media",
        "/srv",
        "/var/home",
    )
    if mount_point.startswith(allowed_prefixes):
        return True

    source = ""
    try:
        source = os.path.realpath(mount_point)
    except OSError:
        source = mount_point

    return source.startswith(allowed_prefixes)


def _linux_mount_sort_key(mount_point: str) -> tuple[int, int, str]:
    priority = 0 if mount_point == "/" else 1
    return (priority, len(mount_point), mount_point)


def _dedupe_linux_mounts(mounts: list[str]) -> list[str]:
    deduped: list[str] = []
    seen_devices: set[tuple[int, int]] = set()

    for mount_point in sorted(mounts, key=_linux_mount_sort_key):
        try:
            st = os.stat(mount_point)
        except OSError:
            deduped.append(mount_point)
            continue

        if not stat.S_ISDIR(st.st_mode):
            continue

        identity = (st.st_dev, st.st_ino)
        if identity in seen_devices:
            continue

        deduped.append(mount_point)
        seen_devices.add(identity)

    return deduped


def linux_drive_display_name(mount_point: str) -> str:
    if is_windows():
        return mount_point
    normalized = mount_point.rstrip("/") or "/"
    if normalized == "/":
        return "System Root (/)"
    if normalized == "/home":
        return "Home"
    if normalized.startswith("/mnt/"):
        tail = normalized[len("/mnt/") :].strip("/")
        return f"Mounted Volume ({tail})" if tail else "Mounted Volume"
    if normalized.startswith("/media/"):
        tail = normalized[len("/media/") :].strip("/")
        if "/" in tail:
            tail = tail.split("/")[-1]
        return f"External Drive ({tail})" if tail else "External Drive"
    if normalized.startswith("/srv/"):
        tail = normalized[len("/srv/") :].strip("/")
        return f"Service Storage ({tail})" if tail else "Service Storage"
    if normalized.startswith("/var/home/"):
        tail = normalized[len("/var/home/") :].strip("/")
        return f"Home Volume ({tail})" if tail else "Home Volume"
    return normalized


def linux_drive_display_kind(mount_point: str) -> str:
    if is_windows():
        return "LOCAL"
    normalized = mount_point.rstrip("/") or "/"
    if normalized == "/":
        return "SYSTEM"
    if normalized in {"/home", "/var/home"} or normalized.startswith(("/home/", "/var/home/")):
        return "HOME"
    if normalized.startswith("/media/"):
        return "EXTERNAL"
    if normalized.startswith("/mnt/"):
        return "MOUNTED"
    if normalized.startswith("/srv/"):
        return "SERVICE"
    return "LOCAL"


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

    return _dedupe_linux_mounts(mounts) or ["/"]


def is_admin() -> bool:
    """Whether the process holds administrative rights on the current platform."""
    if is_windows():
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    try:
        geteuid = getattr(os, "geteuid", None)
        if geteuid is not None:
            return geteuid() == 0
    except Exception:
        pass
    return False


def can_elevate() -> bool:
    """Whether a privilege escalation path exists that will not block on a console."""
    if is_admin():
        return True
    if is_windows():
        return True  # UAC is always available
    return bool(shutil.which("pkexec"))


def elevate() -> bool:
    if is_admin():
        return True
    if is_windows():
        try:
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, _elevation_args(), None, 1
            )
            return True
        except Exception:
            return False
    # polkit shows a graphical authentication dialog; sudo would need a terminal.
    if shutil.which("pkexec"):
        try:
            subprocess.Popen(["pkexec", sys.executable] + sys.argv)
            return True
        except Exception:
            return False
    return False


def _elevation_args() -> str:
    if getattr(sys, "frozen", False):
        return " ".join(f'"{a}"' for a in sys.argv[1:])
    script = Path(sys.argv[0]).resolve()
    args = [f'"{script}"'] + [f'"{a}"' for a in sys.argv[1:]]
    return " ".join(args)


def relaunch_as_admin(argv: list[str] | None = None) -> bool:
    """Restart this application with administrative rights.

    Alias for :func:`elevate`; the old separate implementation ran `runas` on
    `argv[0]`, which is a .py file when running from source.
    """
    return elevate()


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
    """Resolve an executable on PATH, honouring PATHEXT on Windows."""
    return shutil.which(program)


@dataclass(frozen=True)
class CommandResult:
    """Outcome of one external command.

    Mapping access (``result["stdout"]``) is kept for existing call sites.
    A command that never ran carries `error` and a negative `returncode`, so
    failure is never mistaken for empty-but-successful output.
    """

    returncode: int
    stdout: str = ""
    stderr: str = ""
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.returncode == 0

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key) from None

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


def run_command(
    args: list[str],
    timeout: float = 120.0,
    cwd: str | None = None,
    env_extra: dict[str, str] | None = None,
) -> CommandResult:
    """Run `args` to completion and capture its output. Never raises."""
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
            creationflags=(subprocess.CREATE_NO_WINDOW if sys.platform.startswith("win") else 0),
        )
        return CommandResult(
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
        )
    except subprocess.TimeoutExpired as exc:
        raw_out = exc.stdout or ""
        out_text = (
            raw_out.decode("utf-8", errors="replace")
            if isinstance(raw_out, bytes)
            else str(raw_out)
        )
        return CommandResult(returncode=-1, stdout=out_text, stderr="timed out", error="timed out")
    except FileNotFoundError as exc:
        return CommandResult(returncode=-2, stderr=str(exc), error=str(exc))
    except OSError as exc:
        return CommandResult(returncode=-1, stderr=str(exc), error=str(exc))


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


# A root-privileged apt-get/pacman reads an id beginning with a dash as an option.
_PACKAGE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+:@/-]*$")


def safe_package_ids(ids: Iterable[str]) -> list[str]:
    """The subset of `ids` that may be handed to an elevated package manager."""
    return [candidate for candidate in ids if candidate and _PACKAGE_ID.match(candidate)]
