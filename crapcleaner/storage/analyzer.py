"""Hierarchical directory disk usage analyzer and breakdown engine.

Supports drill-down tree traversal, largest directory detection, symbolic link
and Windows junction cycle protection, and cancellation.
"""

import os
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from crapcleaner.utils.platform import is_linux

_REPARSE_POINT = 0x400
_IS_WINDOWS = sys.platform == "win32"


@dataclass
class StorageNode:
    name: str
    path: str
    size: int = 0
    file_count: int = 0
    dir_count: int = 0
    children: list["StorageNode"] = field(default_factory=list)
    percentage_of_parent: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "size": self.size,
            "file_count": self.file_count,
            "dir_count": self.dir_count,
            "percentage_of_parent": round(self.percentage_of_parent, 2),
            "children": [c.to_dict() for c in self.children],
        }


def _is_link_like(entry: os.DirEntry) -> bool:
    """True for symlinks and Windows junctions/reparse points.

    On Windows the reparse flag comes from the directory listing itself, so this
    costs nothing, while resolving a real path costs a syscall.
    """
    try:
        if entry.is_symlink():
            return True
    except OSError:
        return False
    if not _IS_WINDOWS:
        return False
    try:
        return bool(entry.stat(follow_symlinks=False).st_file_attributes & _REPARSE_POINT)
    except (OSError, AttributeError):
        return False


def _child_real_path(entry: os.DirEntry, parent_real: str) -> str:
    if _is_link_like(entry):
        try:
            return os.path.realpath(entry.path)
        except OSError:
            return entry.path
    return os.path.join(parent_real, entry.name)


def _should_skip_linux_subtree(path: str) -> bool:
    if not is_linux():
        return False
    normalized = os.path.normpath(path)
    return normalized in {
        "/proc",
        "/sys",
        "/dev",
        "/run",
        "/var/lib/docker",
        "/var/lib/containers",
    } or normalized.startswith(
        (
            "/proc/",
            "/sys/",
            "/dev/",
            "/run/",
            "/var/lib/docker/",
            "/var/lib/containers/",
        )
    )


def analyze_storage_hierarchy(
    root: str,
    max_depth: int = 3,
    max_children: int = 20,
    stop_event: threading.Event | None = None,
    progress_cb: Callable[[int, str], None] | None = None,
) -> StorageNode | None:
    """Analyze directory structure starting at root and return a hierarchical StorageNode tree."""
    if not root or not os.path.isdir(root):
        return None

    visited_paths: set[str] = set()
    visited_inodes: set[tuple[int, int]] = set()
    total_visited_files = 0

    def _already_visited(real_path: str, entry: os.DirEntry | None) -> bool:
        key = os.path.normcase(real_path)
        if key in visited_paths:
            return True
        visited_paths.add(key)
        # Real paths cannot detect bind mounts or hardlinked directories, which
        # only exist off Windows; there the listing already carries stat data.
        if entry is not None and not _IS_WINDOWS:
            try:
                st = entry.stat(follow_symlinks=False)
                identity = (st.st_dev, st.st_ino)
            except OSError:
                return False
            if identity[1]:
                if identity in visited_inodes:
                    return True
                visited_inodes.add(identity)
        return False

    def _scan_dir(
        current_path: str, current_depth: int, real_path: str, entry: os.DirEntry | None
    ) -> StorageNode:
        nonlocal total_visited_files
        node = StorageNode(
            name=os.path.basename(current_path) or current_path,
            path=current_path,
        )

        if _already_visited(real_path, entry):
            return node

        try:
            with os.scandir(current_path) as it:
                entries = list(it)
        except OSError:
            return node

        subdirs: list[os.DirEntry] = []
        for child in entries:
            if stop_event is not None and stop_event.is_set():
                return node
            try:
                if child.is_dir(follow_symlinks=False):
                    if _should_skip_linux_subtree(child.path):
                        continue
                    subdirs.append(child)
                    node.dir_count += 1
                elif child.is_file(follow_symlinks=False):
                    node.size += child.stat(follow_symlinks=False).st_size
                    node.file_count += 1
                    total_visited_files += 1
                    if progress_cb is not None and total_visited_files % 1000 == 0:
                        progress_cb(total_visited_files, current_path)
            except OSError:
                continue

        child_nodes: list[StorageNode] = []
        for sub_entry in subdirs:
            if stop_event is not None and stop_event.is_set():
                break
            child_node = _scan_dir(
                sub_entry.path,
                current_depth + 1,
                _child_real_path(sub_entry, real_path),
                sub_entry,
            )
            node.size += child_node.size
            node.file_count += child_node.file_count
            node.dir_count += child_node.dir_count
            if current_depth < max_depth:
                child_nodes.append(child_node)

        child_nodes.sort(key=lambda c: c.size, reverse=True)
        if node.size > 0:
            for child_node in child_nodes:
                child_node.percentage_of_parent = (child_node.size / node.size) * 100.0

        node.children = child_nodes[:max_children]
        return node

    try:
        root_real = os.path.realpath(root)
    except OSError:
        root_real = root
    return _scan_dir(root, 0, root_real, None)
