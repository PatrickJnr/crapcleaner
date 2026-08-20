"""Cross-platform Recycle Bin (Windows) and FreeDesktop Trash (Linux) inspector.

Provides read-only inspection of trash contents, total size, item count,
oldest/newest timestamps, item listing, and explicit empty action.
"""

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import unquote

from crapcleaner.utils.files import empty_recycle_bin as _empty_trash
from crapcleaner.utils.platform import get_user_profile, is_linux, is_windows


class _SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("i64Size", ctypes.c_int64),
        ("i64NumItems", ctypes.c_int64),
    ]


@dataclass
class TrashItem:
    name: str
    original_path: str
    size: int
    deleted_at: datetime | None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "original_path": self.original_path,
            "size": self.size,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }


@dataclass
class RecycleBinInfo:
    available: bool
    total_size: int = 0
    item_count: int = 0
    oldest_item: datetime | None = None
    newest_item: datetime | None = None
    items: list[TrashItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "available": self.available,
            "total_size": self.total_size,
            "item_count": self.item_count,
            "oldest_item": self.oldest_item.isoformat() if self.oldest_item else None,
            "newest_item": self.newest_item.isoformat() if self.newest_item else None,
            "items": [item.to_dict() for item in self.items],
        }


def get_recycle_bin_info() -> RecycleBinInfo:
    """Inspect platform trash/recycle bin and return structured metadata."""
    if is_windows():
        return _get_windows_recycle_bin_info()
    if is_linux():
        return _get_linux_trash_info()
    return RecycleBinInfo(available=False)


def _get_windows_recycle_bin_info() -> RecycleBinInfo:
    from crapcleaner.utils.platform import list_drives

    info = RecycleBinInfo(available=True)
    try:
        query_info = _SHQUERYRBINFO()
        query_info.cbSize = ctypes.sizeof(_SHQUERYRBINFO)
        res = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(query_info))
        if res == 0:
            info.total_size = int(query_info.i64Size)
            info.item_count = int(query_info.i64NumItems)
    except Exception:
        pass

    items: list[TrashItem] = []
    oldest: datetime | None = None
    newest: datetime | None = None

    try:
        for drive in list_drives():
            bin_path = os.path.join(drive, "$Recycle.Bin")
            if not os.path.isdir(bin_path):
                continue
            try:
                with os.scandir(bin_path) as it:
                    for sid_entry in it:
                        if sid_entry.is_dir(follow_symlinks=False):
                            try:
                                with os.scandir(sid_entry.path) as sit:
                                    for entry in sit:
                                        if len(items) >= 50:
                                            break
                                        if entry.is_file(follow_symlinks=False):
                                            try:
                                                st = entry.stat(follow_symlinks=False)
                                                mtime = datetime.fromtimestamp(st.st_mtime)
                                                if oldest is None or mtime < oldest:
                                                    oldest = mtime
                                                if newest is None or mtime > newest:
                                                    newest = mtime
                                                items.append(
                                                    TrashItem(
                                                        name=entry.name,
                                                        original_path=entry.path,
                                                        size=st.st_size,
                                                        deleted_at=mtime,
                                                    )
                                                )
                                            except (OSError, PermissionError):
                                                continue
                            except (OSError, PermissionError):
                                continue
            except (OSError, PermissionError):
                continue
    except Exception:
        pass

    info.items = items
    info.oldest_item = oldest
    info.newest_item = newest
    return info


def _get_linux_trash_info() -> RecycleBinInfo:
    info = RecycleBinInfo(available=True)
    user = get_user_profile()
    trash_files_dir = os.path.join(user, ".local", "share", "Trash", "files")
    trash_info_dir = os.path.join(user, ".local", "share", "Trash", "info")

    if not os.path.isdir(trash_files_dir):
        return info

    total_size = 0
    item_count = 0
    items: list[TrashItem] = []
    oldest: datetime | None = None
    newest: datetime | None = None

    try:
        for entry in os.scandir(trash_files_dir):
            try:
                st = entry.stat(follow_symlinks=False)
                sz = st.st_size
                mtime = datetime.fromtimestamp(st.st_mtime)
                orig_path = ""

                info_file = os.path.join(trash_info_dir, f"{entry.name}.trashinfo")
                if os.path.isfile(info_file):
                    try:
                        with open(info_file, encoding="utf-8", errors="replace") as fh:
                            for line in fh:
                                if line.startswith("Path="):
                                    orig_path = unquote(line.split("=", 1)[1].strip())
                                elif line.startswith("DeletionDate="):
                                    d_str = line.split("=", 1)[1].strip()
                                    try:
                                        mtime = datetime.fromisoformat(d_str)
                                    except ValueError:
                                        pass
                    except OSError:
                        pass

                total_size += sz
                item_count += 1

                if oldest is None or mtime < oldest:
                    oldest = mtime
                if newest is None or mtime > newest:
                    newest = mtime

                if len(items) < 100:
                    items.append(
                        TrashItem(
                            name=entry.name,
                            original_path=orig_path or entry.path,
                            size=sz,
                            deleted_at=mtime,
                        )
                    )
            except OSError:
                continue
    except OSError:
        pass

    info.total_size = total_size
    info.item_count = item_count
    info.items = items
    info.oldest_item = oldest
    info.newest_item = newest
    return info


def empty_trash() -> bool:
    """Explicitly empty the Recycle Bin or FreeDesktop Trash."""
    return _empty_trash()
