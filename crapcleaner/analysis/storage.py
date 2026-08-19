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
from queue import Empty, SimpleQueue

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


#: Directories enumerated concurrently. Every directory is queued as its own unit of
#: work, so one oversized subtree - AppData is routinely two thirds of a user profile -
#: cannot leave the other threads idle. Enumeration is dominated by syscalls that
#: release the GIL and, on a cold cache, by per-directory I/O latency that overlaps
#: almost perfectly: measured 16k files/s serial against 52k files/s at this width on
#: an NVMe volume with nothing cached.
_MAX_SCAN_WORKERS = 24


def analyze_storage_hierarchy(
    root: str,
    max_depth: int = 3,
    max_children: int = 20,
    stop_event: threading.Event | None = None,
    progress_cb: Callable[[int, str], None] | None = None,
    max_workers: int = _MAX_SCAN_WORKERS,
    partial_cb: Callable[[StorageNode], None] | None = None,
    partial_interval: float = 1.0,
) -> StorageNode | None:
    """Analyze directory structure starting at root and return a hierarchical StorageNode tree.

    The whole tree is measured regardless of `max_depth`, because a folder's size
    includes everything beneath it; `max_depth` only limits how deep the returned tree
    is kept. Directories are enumerated by a pool of workers pulling from a shared
    queue, and the tree is assembled from the flat results, so the output never depends
    on the order in which directories happened to finish.

    Pass `partial_cb` to receive the tree as it stands every `partial_interval` seconds
    while the scan runs, so a caller can show the largest directories immediately rather
    than waiting for a whole volume to be measured.
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

    def _scan_one(path: str) -> tuple[StorageNode, list[os.DirEntry]]:
        """Enumerate one directory: own-file totals now, sub-directories for the queue."""
        node = StorageNode(name=os.path.basename(path) or path, path=path)
        subdirs: list[os.DirEntry] = []
        try:
            with os.scandir(path) as it:
                for child in it:
                    if stop_event is not None and stop_event.is_set():
                        return node, []
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
                    except OSError:
                        continue
        except OSError:
            return node, []

        if node.file_count:
            _note_files(node.file_count, path)
        return node, subdirs

    nodes: dict[str, StorageNode] = {}
    children_of: dict[str, list[str]] = {}
    parent_of: dict[str, str] = {}
    queue: SimpleQueue = SimpleQueue()
    outstanding = [0]

    def _enqueue(path: str, real_path: str, entry: os.DirEntry | None) -> bool:
        if _already_visited(real_path, entry):
            return False
        with state_lock:
            outstanding[0] += 1
        queue.put((path, real_path))
        return True

    def _roll_up(path: str, node: StorageNode) -> None:
        """Add a finished directory's totals to every ancestor. Caller holds the lock.

        Aggregating as results arrive, rather than summing the tree at the end, is what
        makes a mid-scan snapshot possible: the top of the tree is always correct for
        everything measured so far, and taking a snapshot costs a walk of the shallow
        levels instead of a walk of every directory found.
        """
        parent = parent_of.get(path)
        while parent is not None:
            ancestor = nodes.get(parent)
            if ancestor is None:
                return
            ancestor.size += node.size
            ancestor.file_count += node.file_count
            ancestor.dir_count += node.dir_count
            parent = parent_of.get(parent)

    def _worker() -> None:
        while True:
            try:
                path, real_path = queue.get(timeout=0.1)
            except Empty:
                with state_lock:
                    if outstanding[0] <= 0:
                        return
                continue

            if stop_event is not None and stop_event.is_set():
                with state_lock:
                    outstanding[0] -= 1
                continue

            node, subdirs = _scan_one(path)
            accepted = [
                entry
                for entry in subdirs
                if _enqueue(entry.path, os.path.join(real_path, entry.name), entry)
            ]

            with state_lock:
                nodes[path] = node
                children_of[path] = [entry.path for entry in accepted]
                for entry in accepted:
                    parent_of[entry.path] = path
                _roll_up(path, node)
                outstanding[0] -= 1

    def _assemble(path: str, depth: int) -> StorageNode:
        """Copy the shallow levels of the tree out of the scan's running state.

        Totals are already aggregated, so this only sorts, prunes and computes shares,
        and it never descends past `max_depth` - which is what makes it cheap enough to
        run repeatedly while the scan is still going.
        """
        source = nodes.get(path)
        node = StorageNode(
            name=os.path.basename(path) or path,
            path=path,
            size=source.size if source is not None else 0,
            file_count=source.file_count if source is not None else 0,
            dir_count=source.dir_count if source is not None else 0,
        )
        if depth >= max_depth:
            return node

        child_nodes = [_assemble(child, depth + 1) for child in children_of.get(path, ())]
        child_nodes.sort(key=lambda c: c.size, reverse=True)
        if node.size > 0:
            for child in child_nodes:
                child.percentage_of_parent = (child.size / node.size) * 100.0
        node.children = child_nodes[:max_children]
        return node

    def _snapshot() -> StorageNode:
        with state_lock:
            return _assemble(root, 0)

    try:
        root_real = os.path.realpath(root)
    except OSError:
        root_real = root

    if not _enqueue(root, root_real, None):
        return StorageNode(name=os.path.basename(root) or root, path=root)

    workers = max(1, int(max_workers))
    finished = threading.Event()

    def _publish_partials(callback: Callable[[StorageNode], None]) -> None:
        while not finished.wait(partial_interval):
            if stop_event is not None and stop_event.is_set():
                return
            callback(_snapshot())

    reporter: threading.Thread | None = None
    if partial_cb is not None and partial_interval > 0:
        reporter = threading.Thread(target=_publish_partials, args=(partial_cb,), daemon=True)
        reporter.start()

    try:
        if workers == 1:
            _worker()
        else:
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="storage-scan") as pool:
                list(pool.map(lambda _: _worker(), range(workers)))
    finally:
        finished.set()
        if reporter is not None:
            reporter.join(timeout=1.0)

    return _snapshot()
