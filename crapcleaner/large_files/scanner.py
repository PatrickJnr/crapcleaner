"""Large file scanner ("Find Big Crap")."""

import heapq
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

SKIP_DIR_NAMES = {
    "$Recycle.Bin",
    "System Volume Information",
    "Windows",
    "ProgramData",
    "AppData\\Local\\Microsoft",
    ".git",
    "node_modules",
}

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


def _should_skip_dir(dirpath: str) -> bool:
    lowered = dirpath.lower()
    for skip in SKIP_DIR_NAMES:
        if skip.lower() in lowered:
            return True
    return False


def scan_large_files(
    root: str,
    threshold_bytes: int,
    stop_event: threading.Event | None = None,
    progress_cb: Callable[[int], None] | None = None,
    max_results: int | None = 5000,
) -> list[LargeFile]:
    if not root or not os.path.isdir(root):
        return []
    results: list[LargeFile] = []
    visited = 0

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        if stop_event is not None and stop_event.is_set():
            break
        dirnames[:] = [
            d
            for d in dirnames
            if not os.path.islink(os.path.join(dirpath, d))
            and not _should_skip_dir(os.path.join(dirpath, d))
        ]
        for name in filenames:
            if stop_event is not None and stop_event.is_set():
                break
            full = os.path.join(dirpath, name)
            try:
                st = os.stat(full)
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
            elif len(results) < max_results:
                heapq.heappush(results, (item.size, len(results), item))
            elif item.size > results[0][0]:
                heapq.heapreplace(results, (item.size, visited, item))
        if progress_cb is not None and visited % 2000 == 0:
            progress_cb(visited)

    if max_results is not None and max_results > 0:
        results = [item for _size, _idx, item in sorted(results, reverse=True)]
    else:
        results.sort(key=lambda item: item.size, reverse=True)
    return results
