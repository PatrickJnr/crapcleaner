"""Large file scanner ("Find Big Crap")."""

import heapq
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from crapcleaner.core.protected_paths import DirectoryGuard
from crapcleaner.utils.files import walk_safe_entries
from crapcleaner.utils.platform import get_program_data, get_windows_dir, is_windows

#: Directory names that are skipped wherever they appear. Matched against the
#: directory's own name, never as a substring of the whole path: "Windows" as a
#: substring test also skips `Games\MyGame\WindowsNoEditor`, which is where a
#: large-file scan most needs to look.
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
    ".iso": "Disk image",
    ".vhd": "Virtual disk",
    ".vhdx": "Virtual disk",
    ".zip": "Archive",
    ".rar": "Archive",
    ".7z": "Archive",
    ".tar": "Archive",
    ".gz": "Archive",
    ".mp4": "Video",
    ".mkv": "Video",
    ".avi": "Video",
    ".mp3": "Audio",
    ".flac": "Audio",
    ".wav": "Audio",
    ".png": "Image",
    ".jpg": "Image",
    ".jpeg": "Image",
    ".webp": "Image",
    ".gif": "Image",
    ".gguf": "AI model",
    ".safetensors": "AI model",
    ".onnx": "AI model",
    ".bin": "Binary/data",
    ".pdb": "Debug symbols",
    ".dmp": "Crash dump",
    ".log": "Log file",
    ".db": "Database",
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

    def to_dict(self) -> dict:
        return {
            "category": "large-file",
            "path": self.path,
            "size": self.size,
            "last_modified": self.last_modified.isoformat(timespec="seconds"),
            "extension": self.extension,
            "file_type": self.file_type,
        }


def _file_type(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return FILE_TYPE_MAP.get(ext, "Other")


def _system_scan_roots() -> tuple[str, ...]:
    """Operating system trees a "find big files" scan should not offer up.

    Resolved from the real locations rather than matched by name, so a user folder
    that happens to be called `Windows` is scanned and `C:\\Windows` is not.
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
) -> list[LargeFile]:
    if not root or not os.path.isdir(root):
        return []
    if _should_skip_dir(root):
        return []
    heap: list[tuple[int, int, LargeFile]] = []
    results: list[LargeFile] = []
    visited = 0

    # walk_safe_entries already keeps symlinks and junctions out of the traversal, and
    # prunes skipped directories before listing them. Protected content is filtered
    # here rather than at deletion time, so a credential file is never offered as a
    # deletion candidate in the first place.
    for dirpath, file_entries in walk_safe_entries(root, skip_dir=_should_skip_dir):
        if stop_event is not None and stop_event.is_set():
            break
        guard = DirectoryGuard(dirpath)
        if not guard.directory_allowed:
            continue
        for entry in file_entries:
            if stop_event is not None and stop_event.is_set():
                break
            if not guard.allows_file(entry.name):
                continue
            name = entry.name
            full = entry.path
            try:
                st = entry.stat(follow_symlinks=False)
                visited += 1
            except OSError:
                continue
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
                file_type=_file_type(full),
            )
            if max_results is None or max_results <= 0:
                results.append(item)
            elif len(heap) < max_results:
                heapq.heappush(heap, (item.size, len(heap), item))
            elif item.size > heap[0][0]:
                heapq.heapreplace(heap, (item.size, visited, item))
        if progress_cb is not None and visited % 2000 == 0:
            progress_cb(visited)

    if max_results is not None and max_results > 0:
        results = [item for _size, _idx, item in sorted(heap, reverse=True)]
    else:
        results.sort(key=lambda item: item.size, reverse=True)
    return results
