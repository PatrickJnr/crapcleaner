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

from crapcleaner.utils.disk_size import SIZE_LOGICAL, size_for
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


def _assemble_from(
    nodes: dict[str, "StorageNode"],
    children_of: dict[str, list[str]],
    path: str,
    depth: int,
    max_depth: int,
    max_children: int,
) -> "StorageNode":
    """Copy the shallow levels of a measured tree out of the flat maps.

    Totals are already aggregated, so this only sorts, prunes and computes shares.
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

    child_nodes = [
        _assemble_from(nodes, children_of, child, depth + 1, max_depth, max_children)
        for child in children_of.get(path, ())
    ]
    child_nodes.sort(key=lambda c: c.size, reverse=True)
    if node.size > 0:
        for child in child_nodes:
            child.percentage_of_parent = (child.size / node.size) * 100.0
    node.children = child_nodes[:max_children]
    return node


@dataclass
class StorageIndex:
    """Every directory a scan measured, keyed by path.

    The whole tree is measured regardless of `max_depth`, so keeping the flat maps
    makes expanding a folder a lookup instead of re-walking what was just measured.
    """

    nodes: dict[str, StorageNode] = field(default_factory=dict)
    children: dict[str, list[str]] = field(default_factory=dict)

    def has(self, path: str) -> bool:
        return path in self.nodes

    def subtree(self, path: str, max_depth: int = 2, max_children: int = 20) -> StorageNode | None:
        """The measured subtree at `path`, or None if this scan never reached it."""
        if path not in self.nodes:
            return None
        return _assemble_from(self.nodes, self.children, path, 0, max_depth, max_children)


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


#: Each directory is queued as its own unit of work, so one oversized subtree cannot
#: leave the other threads idle. Enumeration is dominated by GIL-releasing syscalls
#: and I/O latency that overlaps almost perfectly: measured 16k files/s serial against
#: 52k files/s at this width on an uncached NVMe volume.
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
    file_observer: Callable[[os.DirEntry, os.stat_result], None] | None = None,
    index_out: StorageIndex | None = None,
    size_mode: str = SIZE_LOGICAL,
) -> StorageNode | None:
    """Analyze directory structure starting at root and return a hierarchical StorageNode tree.

    The whole tree is measured regardless of `max_depth`, because a folder's size
    includes everything beneath it; `max_depth` only limits how deep the returned tree
    is kept. Workers pull from a shared queue and the tree is assembled from the flat
    results, so the output never depends on the order directories finished in.

    Pass `partial_cb` to receive the tree as it stands every `partial_interval` seconds,
    so a caller can show the largest directories before the volume is fully measured.

    Pass `file_observer` to be handed every file entry and its stat result as they are
    read, sparing other analyses a second traversal. It runs on the scan's worker
    threads, so it must be cheap and thread-safe.

    Pass `index_out` to keep every directory measured, making expansion a lookup.

    `size_mode` selects what a file's size means: `logical` is the length of its
    contents, which every listing already carries; `allocated` is what it occupies on
    disk, which is what free space reflects for compressed, sparse and very small
    files. Allocated mode costs an extra call per file on Windows.
    """
    if not root or not os.path.isdir(root):
        return None

    visited_paths: set[str] = set()
    visited_inodes: set[tuple[int, int]] = set()
    total_visited_files = 0
    # Guards the shared visited sets and the progress counter; each critical section is
    # a set lookup, far cheaper than the syscalls around it.
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
                            # Descending a junction bills another drive's bytes here.
                            if is_link_like(child) or _should_skip_linux_subtree(child.path):
                                continue
                            subdirs.append(child)
                            node.dir_count += 1
                        elif child.is_file(follow_symlinks=False):
                            st = child.stat(follow_symlinks=False)
                            node.size += (
                                st.st_size
                                if size_mode == SIZE_LOGICAL
                                else size_for(child.path, st, size_mode)
                            )
                            node.file_count += 1
                            if file_observer is not None:
                                file_observer(child, st)
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

    def _claim(real_path: str, entry: os.DirEntry | None) -> bool:
        """Reserve a directory for scanning without making it runnable yet.

        A child queued before its parent records `parent_of[child]` can finish first
        and find no ancestor to bill, losing its bytes; the caller must publish the
        link and the parent node before calling `queue.put`.
        """
        if _already_visited(real_path, entry):
            return False
        with state_lock:
            outstanding[0] += 1
        return True

    def _roll_up(path: str, node: StorageNode) -> None:
        """Add a finished directory's totals to every ancestor. Caller holds the lock.

        Aggregating as results arrive is what makes a mid-scan snapshot possible and
        cheap: the top of the tree is always correct for everything measured so far.
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
                entry for entry in subdirs if _claim(os.path.join(real_path, entry.name), entry)
            ]

            with state_lock:
                nodes[path] = node
                children_of[path] = [entry.path for entry in accepted]
                for entry in accepted:
                    parent_of[entry.path] = path
                _roll_up(path, node)
                outstanding[0] -= 1

            for entry in accepted:
                queue.put((entry.path, os.path.join(real_path, entry.name)))

    def _snapshot() -> StorageNode:
        """A consistent view of the shallow levels, assembled outside the lock.

        Holding the lock for the whole assembly stalled every worker once a second.
        """
        with state_lock:
            shallow_nodes: dict[str, StorageNode] = {}
            shallow_children: dict[str, list[str]] = {}
            frontier = [(root, 0)]
            while frontier:
                path, depth = frontier.pop()
                source = nodes.get(path)
                if source is not None:
                    shallow_nodes[path] = StorageNode(
                        name=source.name,
                        path=source.path,
                        size=source.size,
                        file_count=source.file_count,
                        dir_count=source.dir_count,
                    )
                if depth >= max_depth:
                    continue
                children = list(children_of.get(path, ()))
                shallow_children[path] = children
                frontier.extend((child, depth + 1) for child in children)
        return _assemble_from(shallow_nodes, shallow_children, root, 0, max_depth, max_children)

    try:
        root_real = os.path.realpath(root)
    except OSError:
        root_real = root

    if not _claim(root_real, None):
        return StorageNode(name=os.path.basename(root) or root, path=root)
    queue.put((root, root_real))

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

    if index_out is not None:
        with state_lock:
            index_out.nodes = dict(nodes)
            index_out.children = {path: list(kids) for path, kids in children_of.items()}

    return _snapshot()
