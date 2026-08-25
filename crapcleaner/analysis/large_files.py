"""Large file scanner ("Find Big Crap")."""

import heapq
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from crapcleaner.core.protected_paths import GuardStack
from crapcleaner.utils.files import walk_safe_entries

#: Skipped wherever they appear. Matched against the directory's own name, never as a
from crapcleaner.utils.format import format_size
from crapcleaner.utils.platform import get_program_data, get_windows_dir, is_windows

#: Skipped wherever they appear. Matched against the directory's own name, never as a
#: substring of the path: that would also skip `Games\MyGame\WindowsNoEditor`.
SKIP_DIR_NAMES = frozenset(
    {
        "$recycle.bin",
        "system volume information",
        ".git",
        "node_modules",
    }
)

FILE_TYPE_MAP = {
    ".exe": "Executable",
    ".dll": "Dynamic library",
    ".msi": "Installer",
    ".msix": "Installer",
    ".appimage": "Executable",
    ".deb": "Installer",
    ".rpm": "Installer",
    ".iso": "Disk image",
    ".wim": "Disk image",
    ".esd": "Disk image",
    ".vhd": "Virtual disk",
    ".vhdx": "Virtual disk",
    ".vdi": "Virtual disk",
    ".vmdk": "Virtual disk",
    ".qcow2": "Virtual disk",
    ".raw": "Disk image",
    ".img": "Disk image",
    ".zip": "Archive",
    ".rar": "Archive",
    ".7z": "Archive",
    ".tar": "Archive",
    ".gz": "Archive",
    ".bz2": "Archive",
    ".xz": "Archive",
    ".zst": "Archive",
    ".tgz": "Archive",
    ".mp4": "Video",
    ".mkv": "Video",
    ".avi": "Video",
    ".mov": "Video",
    ".wmv": "Video",
    ".webm": "Video",
    ".mp3": "Audio",
    ".flac": "Audio",
    ".wav": "Audio",
    ".opus": "Audio",
    ".m4a": "Audio",
    ".png": "Image",
    ".jpg": "Image",
    ".jpeg": "Image",
    ".webp": "Image",
    ".gif": "Image",
    ".heic": "Image",
    ".avif": "Image",
    ".jxl": "Image",
    ".gguf": "AI model",
    ".safetensors": "AI model",
    ".onnx": "AI model",
    ".pt": "AI model",
    ".pth": "AI model",
    ".ckpt": "AI model",
    ".tflite": "AI model",
    ".bin": "Binary/data",
    ".pdb": "Debug symbols",
    ".dmp": "Crash dump",
    ".log": "Log file",
    ".db": "Database",
    ".sqlite": "Database",
    ".sqlite3": "Database",
    ".parquet": "Data file",
    ".arrow": "Data file",
    ".pkl": "Pickle data",
    ".npy": "NumPy array",
    ".blend": "Blender file",
    ".fbx": "3D model",
    ".uasset": "Unreal asset",
    ".pak": "Game package",
}


@dataclass
class LargeFile:
    path: str
    size: int
    last_modified: datetime
    extension: str
    file_type: str

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    @property
    def human_size(self) -> str:
        return format_size(self.size)

    def to_dict(self) -> dict:
        return {
            "category": "large-file",
            "path": self.path,
            "size": self.size,
            "human_size": self.human_size,
            "last_modified": self.last_modified.isoformat(timespec="seconds")
            if self.last_modified
            else None,
            "extension": self.extension,
            "file_type": self.file_type,
        }


def _file_type(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return FILE_TYPE_MAP.get(ext, "Other")


def _system_scan_roots() -> tuple[str, ...]:
    """Operating system trees a "find big files" scan should not offer up.

    Resolved from real locations, not matched by name, so a user folder called
    `Windows` is still scanned.
    """
    global _SYSTEM_ROOTS
    if _SYSTEM_ROOTS is None:
        roots: list[str] = []
        if is_windows():
            for candidate in (get_windows_dir(), get_program_data()):
                if candidate:
                    roots.append(os.path.normcase(os.path.abspath(candidate)))
        else:
            roots.extend(["/proc", "/sys", "/dev", "/run"])
        _SYSTEM_ROOTS = tuple(roots)
    return _SYSTEM_ROOTS


_SYSTEM_ROOTS: tuple[str, ...] | None = None


def _should_skip_dir(dirpath: str) -> bool:
    name = os.path.basename(dirpath.rstrip("\\/")).lower()
    if name in SKIP_DIR_NAMES:
        return True
    normalized = os.path.normcase(os.path.abspath(dirpath))
    return any(
        normalized == root or normalized.startswith(root + os.sep) for root in _system_scan_roots()
    )


def scan_large_files(
    root: str,
    threshold_bytes: int,
    stop_event: threading.Event | None = None,
    progress_cb: Callable[[int], None] | None = None,
    max_results: int | None = 5000,
    category_filter: set[str] | list[str] | None = None,
    extension_filter: set[str] | list[str] | None = None,
) -> list[LargeFile]:
    """Scan a root folder for files above threshold_bytes with optional category/extension filtering."""
    if not root or not os.path.isdir(root):
        return []
    if _should_skip_dir(root):
        return []
    heap: list[tuple[int, int, LargeFile]] = []
    results: list[LargeFile] = []
    visited = 0

    cat_filters = {c.lower() for c in category_filter} if category_filter else None
    ext_filters = {e.lower().lstrip(".") for e in extension_filter} if extension_filter else None

    # Protected content is filtered here, not at deletion time, so a credential file is
    # never offered as a deletion candidate in the first place.
    guards = GuardStack()
    for dirpath, file_entries in walk_safe_entries(root, skip_dir=_should_skip_dir):
        if stop_event is not None and stop_event.is_set():
            break
        guard = guards.guard_for(dirpath)
        if not guard.directory_allowed:
            continue
        for entry in file_entries:
            if stop_event is not None and stop_event.is_set():
                break
            if not guard.allows_file(entry.name):
                continue
            ext_normalized = os.path.splitext(entry.name)[1].lower().lstrip(".")
            if ext_filters is not None and ext_normalized not in ext_filters:
                continue
            file_cat = _file_type(entry.path)
            if cat_filters is not None and file_cat.lower() not in cat_filters:
                continue

            name = entry.name
            full = entry.path
            try:
                st = entry.stat(follow_symlinks=False)
                visited += 1
            except OSError:
                continue
            if progress_cb is not None and visited % 2000 == 0:
                progress_cb(visited)
            if st.st_size < threshold_bytes:
                continue
            try:
                mtime = datetime.fromtimestamp(st.st_mtime)
            except (OSError, ValueError, OverflowError):
                mtime = datetime.fromtimestamp(0)
            item = LargeFile(
                path=full,
                size=st.st_size,
                last_modified=mtime,
                extension=os.path.splitext(name)[1].lower(),
                file_type=file_cat,
            )
            if max_results is None or max_results <= 0:
                results.append(item)
            elif len(heap) < max_results:
                heapq.heappush(heap, (item.size, len(heap), item))
            elif item.size > heap[0][0]:
                heapq.heapreplace(heap, (item.size, visited, item))

    if max_results is not None and max_results > 0:
        results = [item for _size, _idx, item in sorted(heap, reverse=True)]
    else:
        results.sort(key=lambda item: item.size, reverse=True)
    return results


def scan_large_files_multi(
    roots: list[str],
    threshold_bytes: int,
    stop_event: threading.Event | None = None,
    progress_cb: Callable[[int], None] | None = None,
    max_results: int | None = 5000,
    category_filter: set[str] | list[str] | None = None,
    extension_filter: set[str] | list[str] | None = None,
) -> list[LargeFile]:
    """Scan across multiple directories or drive mount points for large files."""
    all_files: list[LargeFile] = []
    visited_total = 0

    def _sub_progress(count: int) -> None:
        nonlocal visited_total
        visited_total += count
        if progress_cb is not None:
            progress_cb(visited_total)

    for root in roots:
        if stop_event is not None and stop_event.is_set():
            break
        files = scan_large_files(
            root=root,
            threshold_bytes=threshold_bytes,
            stop_event=stop_event,
            progress_cb=_sub_progress,
            max_results=max_results,
            category_filter=category_filter,
            extension_filter=extension_filter,
        )
        all_files.extend(files)

    all_files.sort(key=lambda item: item.size, reverse=True)
    if max_results is not None and max_results > 0:
        return all_files[:max_results]
    return all_files

