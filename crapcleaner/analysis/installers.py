"""Potentially removable installer and package archive detector.

Scans user directories (Downloads, Desktop) for installation packages (.msi, .exe,
.msix, .appx, .iso, .deb, .rpm, .pkg, .dmg) without assuming they are safe to delete.
Provides non-destructive metadata reporting requiring explicit user selection.
"""

import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from crapcleaner.utils.platform import get_user_profile

_INSTALLER_EXTENSIONS = frozenset(
    {
        ".msi",
        ".msix",
        ".appx",
        ".iso",
        ".pkg",
        ".dmg",
        ".deb",
        ".rpm",
        ".appimage",
    }
)

_INSTALLER_NAME_KEYWORDS = (
    "setup",
    "install",
    "installer",
    "update",
    "patch",
    "downloader",
    "x64",
    "x86",
    "win64",
    "win32",
    "amd64",
    "portable",
)


@dataclass
class InstallerItem:
    filename: str
    path: str
    size: int
    modified_at: datetime
    extension: str
    classification: str = "Potentially removable installer"

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "path": self.path,
            "size": self.size,
            "modified_at": self.modified_at.isoformat(),
            "extension": self.extension,
            "classification": self.classification,
        }


def _is_installer_file(name: str, parent_dir: str) -> bool:
    lowered = name.lower()
    ext = os.path.splitext(lowered)[1]
    if ext in _INSTALLER_EXTENSIONS:
        return True
    if ext == ".exe":
        # In Downloads folder, executables are almost always downloaded installers
        if "download" in parent_dir.lower():
            return True
        if any(kw in lowered for kw in _INSTALLER_NAME_KEYWORDS):
            return True
    return False


def scan_installers(
    search_roots: list[str] | None = None,
    stop_event: threading.Event | None = None,
    progress_cb: Callable[[int, str], None] | None = None,
) -> list[InstallerItem]:
    """Scan user folders for installer packages."""
    user = get_user_profile()
    if not search_roots:
        search_roots = [
            os.path.join(user, "Downloads"),
            os.path.join(user, "Desktop"),
        ]

    items: list[InstallerItem] = []
    visited_files = 0

    for root in search_roots:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root, topdown=True):
            if stop_event is not None and stop_event.is_set():
                break
            dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]

            for name in filenames:
                if stop_event is not None and stop_event.is_set():
                    break
                full = os.path.join(dirpath, name)
                visited_files += 1
                if not _is_installer_file(name, dirpath):
                    continue
                try:
                    st = os.stat(full)
                    mtime = datetime.fromtimestamp(st.st_mtime)
                    items.append(
                        InstallerItem(
                            filename=name,
                            path=full,
                            size=st.st_size,
                            modified_at=mtime,
                            extension=os.path.splitext(name)[1].lower(),
                        )
                    )
                except (OSError, PermissionError):
                    continue

                if progress_cb is not None and visited_files % 500 == 0:
                    progress_cb(visited_files, dirpath)

    items.sort(key=lambda item: item.size, reverse=True)
    return items
