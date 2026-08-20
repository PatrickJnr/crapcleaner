"""File-type and extension storage breakdown analyzer.

Classifies files into intuitive categories (Images, Videos, Audio, Archives,
Executables, Documents, Game files, Developer files, Virtual Machines, AI models)
and calculates aggregate sizes and file counts.
"""

import os
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from crapcleaner.utils.files import walk_safe_entries

FILE_CATEGORY_MAP: dict[str, str] = {
    # Images
    ".png": "Images",
    ".jpg": "Images",
    ".jpeg": "Images",
    ".gif": "Images",
    ".webp": "Images",
    ".svg": "Images",
    ".bmp": "Images",
    ".tiff": "Images",
    ".tif": "Images",
    ".ico": "Images",
    ".raw": "Images",
    ".cr2": "Images",
    ".nef": "Images",
    ".heic": "Images",
    ".avif": "Images",
    # Videos
    ".mp4": "Videos",
    ".mkv": "Videos",
    ".avi": "Videos",
    ".mov": "Videos",
    ".wmv": "Videos",
    ".flv": "Videos",
    ".webm": "Videos",
    ".m4v": "Videos",
    ".3gp": "Videos",
    ".mpg": "Videos",
    ".mpeg": "Videos",
    # Audio
    ".mp3": "Audio",
    ".flac": "Audio",
    ".wav": "Audio",
    ".aac": "Audio",
    ".ogg": "Audio",
    ".m4a": "Audio",
    ".wma": "Audio",
    ".opus": "Audio",
    ".aiff": "Audio",
    ".alac": "Audio",
    ".mid": "Audio",
    ".midi": "Audio",
    # Archives
    ".zip": "Archives",
    ".rar": "Archives",
    ".7z": "Archives",
    ".tar": "Archives",
    ".gz": "Archives",
    ".bz2": "Archives",
    ".xz": "Archives",
    ".zst": "Archives",
    ".cab": "Archives",
    ".tgz": "Archives",
    # Executables & Installers
    ".exe": "Executables",
    ".msi": "Executables",
    ".msix": "Executables",
    ".appx": "Executables",
    ".dll": "Executables",
    ".sys": "Executables",
    ".apk": "Executables",
    ".appimage": "Executables",
    ".deb": "Executables",
    ".rpm": "Executables",
    ".dmg": "Executables",
    ".pkg": "Executables",
    # Documents
    ".pdf": "Documents",
    ".doc": "Documents",
    ".docx": "Documents",
    ".xls": "Documents",
    ".xlsx": "Documents",
    ".ppt": "Documents",
    ".pptx": "Documents",
    ".txt": "Documents",
    ".rtf": "Documents",
    ".odt": "Documents",
    ".ods": "Documents",
    ".odp": "Documents",
    ".csv": "Documents",
    ".md": "Documents",
    ".epub": "Documents",
    # Game files
    ".pak": "Game files",
    ".uasset": "Game files",
    ".bik": "Game files",
    ".vpk": "Game files",
    ".bsa": "Game files",
    ".ba2": "Game files",
    ".wad": "Game files",
    ".big": "Game files",
    ".unity3d": "Game files",
    # Developer files
    ".py": "Developer files",
    ".js": "Developer files",
    ".ts": "Developer files",
    ".rs": "Developer files",
    ".go": "Developer files",
    ".cs": "Developer files",
    ".cpp": "Developer files",
    ".c": "Developer files",
    ".h": "Developer files",
    ".hpp": "Developer files",
    ".java": "Developer files",
    ".json": "Developer files",
    ".yaml": "Developer files",
    ".yml": "Developer files",
    ".toml": "Developer files",
    ".xml": "Developer files",
    ".sql": "Developer files",
    ".html": "Developer files",
    ".css": "Developer files",
    ".scss": "Developer files",
    ".sh": "Developer files",
    ".bat": "Developer files",
    ".ps1": "Developer files",
    # Disk images & VMs
    ".iso": "Virtual machines & Disks",
    ".vhd": "Virtual machines & Disks",
    ".vhdx": "Virtual machines & Disks",
    ".vmdk": "Virtual machines & Disks",
    ".vdi": "Virtual machines & Disks",
    ".qcow2": "Virtual machines & Disks",
    ".ova": "Virtual machines & Disks",
    ".ovf": "Virtual machines & Disks",
    ".img": "Virtual machines & Disks",
    # AI models & data
    ".gguf": "AI models & Data",
    ".safetensors": "AI models & Data",
    ".onnx": "AI models & Data",
    ".bin": "AI models & Data",
    ".pth": "AI models & Data",
    ".pt": "AI models & Data",
    ".ckpt": "AI models & Data",
    ".npy": "AI models & Data",
    ".pkl": "AI models & Data",
    ".h5": "AI models & Data",
    ".tflite": "AI models & Data",
}


@dataclass
class FileTypeSummary:
    category: str
    total_size: int = 0
    file_count: int = 0
    percentage: float = 0.0
    extensions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "total_size": self.total_size,
            "file_count": self.file_count,
            "percentage": round(self.percentage, 2),
            "extensions": self.extensions,
        }


@dataclass
class _GroupStats:
    size: int = 0
    count: int = 0
    extensions: set[str] = field(default_factory=set)


class FileTypeCollector:
    """Accumulates the breakdown from files handed to it, from any number of threads.

    The Storage view used to walk the tree a second time to build this. It now
    subscribes to the hierarchy scan's traversal instead, which runs on a pool - so
    each thread accumulates into its own dict and they are merged at the end rather
    than contending on a lock per file.
    """

    __slots__ = ("_local", "_per_thread", "_lock")

    def __init__(self) -> None:
        self._local = threading.local()
        self._per_thread: list[dict[str, _GroupStats]] = []
        self._lock = threading.Lock()

    def _groups(self) -> dict[str, _GroupStats]:
        groups = getattr(self._local, "groups", None)
        if groups is None:
            groups = {}
            self._local.groups = groups
            with self._lock:
                self._per_thread.append(groups)
        return groups

    def observe(self, name: str, size: int) -> None:
        ext = os.path.splitext(name)[1].lower()
        category = FILE_CATEGORY_MAP.get(ext, "Other")
        groups = self._groups()
        group = groups.get(category)
        if group is None:
            group = _GroupStats()
            groups[category] = group
        group.size += size
        group.count += 1
        if ext:
            group.extensions.add(ext)

    def summaries(self) -> list[FileTypeSummary]:
        merged: dict[str, _GroupStats] = {}
        with self._lock:
            per_thread = list(self._per_thread)
        for groups in per_thread:
            for category, stats in groups.items():
                target = merged.get(category)
                if target is None:
                    target = _GroupStats()
                    merged[category] = target
                target.size += stats.size
                target.count += stats.count
                target.extensions |= stats.extensions
        return _summaries_from(merged)


def _summaries_from(groups: dict[str, _GroupStats]) -> list[FileTypeSummary]:
    total_bytes = sum(stats.size for stats in groups.values())
    summaries = [
        FileTypeSummary(
            category=category,
            total_size=stats.size,
            file_count=stats.count,
            percentage=(stats.size / total_bytes * 100.0) if total_bytes > 0 else 0.0,
            extensions=sorted(stats.extensions),
        )
        for category, stats in groups.items()
    ]
    summaries.sort(key=lambda s: s.total_size, reverse=True)
    return summaries


def analyze_file_types(
    root: str,
    stop_event: threading.Event | None = None,
    progress_cb: Callable[[int, str], None] | None = None,
) -> list[FileTypeSummary]:
    """Scan root and group storage by functional file categories.

    Kept for callers that only want this one breakdown (the CLI). The Storage view
    shares the hierarchy scan's traversal through :class:`FileTypeCollector`.
    """
    if not root or not os.path.isdir(root):
        return []

    groups: dict[str, _GroupStats] = {}
    visited_files = 0

    # walk_safe_entries hands back the DirEntry objects from the directory listing,
    # which already carry the size. Re-stat'ing each file by path cost one syscall per
    # file and dominated the whole Storage Breakdown view.
    for dirpath, file_entries in walk_safe_entries(root):
        if stop_event is not None and stop_event.is_set():
            break

        for entry in file_entries:
            if stop_event is not None and stop_event.is_set():
                break
            try:
                sz = entry.stat(follow_symlinks=False).st_size
            except OSError:
                continue
            visited_files += 1

            ext = os.path.splitext(entry.name)[1].lower()
            category = FILE_CATEGORY_MAP.get(ext, "Other")

            group = groups.get(category)
            if group is None:
                group = _GroupStats()
                groups[category] = group

            group.size += sz
            group.count += 1
            if ext:
                group.extensions.add(ext)

            if progress_cb is not None and visited_files % 1500 == 0:
                progress_cb(visited_files, dirpath)

    return _summaries_from(groups)
