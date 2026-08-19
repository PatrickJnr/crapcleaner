"""Hierarchical directory disk usage analyzer and breakdown engine.

Supports drill-down tree traversal, largest directory detection, symbolic link
and Windows junction cycle protection, and cancellation.
"""

import os
import sys
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from crapcleaner.utils.files import is_link_like
from crapcleaner.utils.platform import is_linux

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


def _child_real_path(entry: os.DirEntry, parent_real: str) -> str:
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


#: Top-level subtrees scanned concurrently. Directory enumeration is dominated by
#: syscalls that release the GIL, so threads genuinely overlap here. The number is
#: deliberately modest: more threads help an NVMe drive but cause seek contention on a
#: spinning disk, and the win flattens out well before this.
_MAX_SCAN_WORKERS = 8


def analyze_storage_hierarchy(
    root: str,
    max_depth: int = 3,
    max_children: int = 20,
    stop_event: threading.Event | None = None,
    progress_cb: Callable[[int, str], None] | None = None,
    max_workers: int = _MAX_SCAN_WORKERS,
) -> StorageNode | None:
    """Analyze directory structure starting at root and return a hierarchical StorageNode tree.

    The whole tree is measured regardless of `max_depth`, because a folder's size
    includes everything beneath it; `max_depth` only limits how deep the returned tree
    is kept. Top-level subtrees are walked in parallel, and results are summed and
    re-sorted afterwards, so the output does not depend on completion order.
    """
    if not root or not os.path.isdir(root):
        return None

    visited_paths: set[str] = set()
    visited_inodes: set[tuple[int, int]] = set()
    total_visited_files = 0
    # Guards the shared visited sets and the progress counter. The critical sections
    # are a set lookup each, orders of magnitude cheaper than the syscalls around them.
    state_lock = threading.Lock()

    def _already_visited(real_path: str, entry: os.DirEntry | None) -> bool:
        key = os.path.normcase(real_path)
        identity = None
        # Real paths cannot detect bind mounts or hardlinked directories, which
        # only exist off Windows; there the listing already carries stat data.
        if entry is not None and not _IS_WINDOWS:
            try:
                st = entry.stat(follow_symlinks=False)
                if st.st_ino:
                    identity = (st.st_dev, st.st_ino)
            except OSError:
                identity = None

        with state_lock:
            if key in visited_paths:
                return True
            visited_paths.add(key)
            if identity is not None:
                if identity in visited_inodes:
                    return True
                visited_inodes.add(identity)
        return False

    def _note_files(count: int, where: str) -> None:
        nonlocal total_visited_files
        if progress_cb is None:
            return
        with state_lock:
            total_visited_files += count
            reached = total_visited_files
        progress_cb(reached, where)

    def _scan_dir(
        current_path: str,
        current_depth: int,
        real_path: str,
        entry: os.DirEntry | None,
        pool: ThreadPoolExecutor | None = None,
    ) -> StorageNode:
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
        local_files = 0
        for child in entries:
            if stop_event is not None and stop_event.is_set():
                return node
            try:
                if child.is_dir(follow_symlinks=False):
                    # A junction or symlink points at data that lives elsewhere;
                    # descending would bill another drive's bytes to this one.
                    if is_link_like(child) or _should_skip_linux_subtree(child.path):
                        continue
                    subdirs.append(child)
                    node.dir_count += 1
                elif child.is_file(follow_symlinks=False):
                    node.size += child.stat(follow_symlinks=False).st_size
                    node.file_count += 1
                    local_files += 1
            except OSError:
                continue

        if local_files:
            _note_files(local_files, current_path)

        # Only the top level fans out. Handing every level to the pool would queue
        # hundreds of thousands of tiny tasks and cost more in scheduling than it saves.
        if pool is not None and subdirs:
            futures = [
                pool.submit(
                    _scan_dir,
                    sub.path,
                    current_depth + 1,
                    _child_real_path(sub, real_path),
                    sub,
                    None,
                )
                for sub in subdirs
            ]
            child_results = [f.result() for f in futures]
        else:
            child_results = []
            for sub_entry in subdirs:
                if stop_event is not None and stop_event.is_set():
                    break
                child_results.append(
                    _scan_dir(
                        sub_entry.path,
                        current_depth + 1,
                        _child_real_path(sub_entry, real_path),
                        sub_entry,
                        None,
                    )
                )

        child_nodes: list[StorageNode] = []
        for child_node in child_results:
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

    workers = max(1, int(max_workers))
    if workers == 1:
        return _scan_dir(root, 0, root_real, None, None)

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="storage-scan") as pool:
        return _scan_dir(root, 0, root_real, None, pool)
