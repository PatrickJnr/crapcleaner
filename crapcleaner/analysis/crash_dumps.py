"""Memory dump and crash dump analysis and grouping engine.

Identifies user-mode crash dumps, kernel minidumps, and system memory dumps,
groups them by application or crash type, and extracts creation/modified timestamps.
"""

import os
import re
from dataclasses import dataclass
from datetime import datetime

from crapcleaner.utils.platform import (
    get_local_appdata,
    get_windows_dir,
    is_linux,
    is_windows,
)


@dataclass
class CrashDumpItem:
    path: str
    filename: str
    size: int
    application: str
    created_at: datetime | None
    modified_at: datetime | None
    dump_type: str  # User-mode, Kernel minidump, Full memory dump, System coredump

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "filename": self.filename,
            "size": self.size,
            "application": self.application,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
            "dump_type": self.dump_type,
        }


def _extract_app_name(filename: str) -> str:
    """Extract application binary name from crash dump filename."""
    # Pattern: app.exe.1234.dmp or app_1234.dmp
    match = re.match(r"^([a-zA-Z0-9_\-\.]+?\.exe)", filename, re.IGNORECASE)
    if match:
        return match.group(1)
    parts = filename.split(".")
    if len(parts) > 1 and parts[0]:
        return parts[0]
    return "System / Unknown"


def find_application_dump_paths() -> list[str]:
    """User-mode dump files, which the owning account can delete unaided."""
    return [d.path for d in find_crash_dumps() if d.dump_type == "User-mode crash dump"]


def find_kernel_dump_paths() -> list[str]:
    """Kernel and full-memory dumps. These need elevation and are worth reviewing:
    a single MEMORY.DMP is routinely several gigabytes."""
    return [d.path for d in find_crash_dumps() if d.dump_type != "User-mode crash dump"]


def total_dump_size() -> int:
    return sum(d.size for d in find_crash_dumps())


def find_crash_dumps() -> list[CrashDumpItem]:
    """Scan platform crash dump and minidump locations and return structured items."""
    dumps: list[CrashDumpItem] = []

    if is_windows():
        local = get_local_appdata()
        windir = get_windows_dir()

        scan_targets = [
            (os.path.join(local, "CrashDumps"), "User-mode crash dump"),
            (os.path.join(windir, "Minidump"), "Kernel minidump"),
            (os.path.join(windir, "LiveKernelReports"), "Live kernel report"),
        ]

        for target_dir, dump_label in scan_targets:
            if not os.path.isdir(target_dir):
                continue
            try:
                for entry in os.scandir(target_dir):
                    if entry.is_file(follow_symlinks=False) and entry.name.lower().endswith(
                        (".dmp", ".mdmp", ".hdmp")
                    ):
                        try:
                            st = entry.stat(follow_symlinks=False)
                            mtime = datetime.fromtimestamp(st.st_mtime)
                            try:
                                ctime = datetime.fromtimestamp(st.st_ctime)
                            except (OSError, ValueError):
                                ctime = mtime
                            dumps.append(
                                CrashDumpItem(
                                    path=entry.path,
                                    filename=entry.name,
                                    size=st.st_size,
                                    application=_extract_app_name(entry.name),
                                    created_at=ctime,
                                    modified_at=mtime,
                                    dump_type=dump_label,
                                )
                            )
                        except (OSError, PermissionError):
                            continue
            except (OSError, PermissionError):
                continue

        # Single MEMORY.DMP check
        mem_dmp = os.path.join(windir, "MEMORY.DMP")
        if os.path.isfile(mem_dmp):
            try:
                st = os.stat(mem_dmp)
                dumps.append(
                    CrashDumpItem(
                        path=mem_dmp,
                        filename="MEMORY.DMP",
                        size=st.st_size,
                        application="Windows Kernel",
                        created_at=datetime.fromtimestamp(st.st_ctime),
                        modified_at=datetime.fromtimestamp(st.st_mtime),
                        dump_type="Full memory dump",
                    )
                )
            except OSError:
                pass

    elif is_linux():
        for candidate_dir in ("/var/crash", "/var/lib/systemd/coredump"):
            if not os.path.isdir(candidate_dir):
                continue
            try:
                for entry in os.scandir(candidate_dir):
                    if entry.is_file(follow_symlinks=False):
                        try:
                            st = entry.stat(follow_symlinks=False)
                            mtime = datetime.fromtimestamp(st.st_mtime)
                            dumps.append(
                                CrashDumpItem(
                                    path=entry.path,
                                    filename=entry.name,
                                    size=st.st_size,
                                    application=_extract_app_name(entry.name),
                                    created_at=mtime,
                                    modified_at=mtime,
                                    dump_type="System coredump",
                                )
                            )
                        except OSError:
                            continue
            except OSError:
                continue

    dumps.sort(key=lambda d: d.size, reverse=True)
    return dumps
