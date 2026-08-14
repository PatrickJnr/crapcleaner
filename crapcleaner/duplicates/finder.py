"""Duplicate file finder with multi-stage hashing and parallel I/O.

Stages:
1. Size-based grouping: Files with unique sizes cannot be duplicates.
2. Fast prefix hashing: Read the first 8 KB to eliminate files with different headers.
3. Full SHA-256 hashing: Only computed for files sharing both identical size and prefix hash.
"""

import hashlib
import os
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

_PREFIX_SIZE = 8192  # 8 KB prefix
_HASH_CHUNK_SIZE = 1024 * 1024  # 1 MB chunk


@dataclass
class DuplicateGroup:
    size: int
    files: list[str] = field(default_factory=list)

    @property
    def duplicate_count(self) -> int:
        return max(0, len(self.files) - 1)

    @property
    def reclaimable(self) -> int:
        return self.duplicate_count * self.size

    def to_dict(self) -> dict:
        return {
            "size": self.size,
            "duplicate_count": self.duplicate_count,
            "reclaimable": self.reclaimable,
            "files": self.files,
        }


def _hash_prefix(path: str, prefix_size: int = _PREFIX_SIZE) -> str | None:
    """Read and hash only the first few kilobytes of a file."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(prefix_size)
            if not chunk:
                return None
            h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _hash_full_file(path: str, chunk_size: int = _HASH_CHUNK_SIZE) -> str | None:
    """Compute the full SHA-256 checksum of a file."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def find_duplicates(
    folders: list[str],
    min_size_bytes: int,
    stop_event: threading.Event | None = None,
    progress_cb: Callable[[int, int], None] | None = None,
    max_workers: int = 4,
) -> list[DuplicateGroup]:
    """Find duplicate files across one or more root folders using multi-stage hashing."""
    by_size: dict[int, list[str]] = {}
    visited = 0

    # Stage 1: Walk directories and group by size
    for folder in folders:
        if not folder or not os.path.isdir(folder):
            continue
        for dirpath, dirnames, filenames in os.walk(folder, topdown=True):
            if stop_event is not None and stop_event.is_set():
                return []
            dirnames[:] = [d for d in dirnames if not os.path.islink(os.path.join(dirpath, d))]
            for name in filenames:
                if stop_event is not None and stop_event.is_set():
                    return []
                full = os.path.join(dirpath, name)
                try:
                    st = os.stat(full)
                    visited += 1
                except OSError:
                    continue
                if st.st_size < min_size_bytes:
                    continue
                by_size.setdefault(st.st_size, []).append(full)
                if progress_cb is not None and visited % 2000 == 0:
                    progress_cb(visited, 0)

    # Filter to only sizes with 2 or more files
    size_candidates = {size: paths for size, paths in by_size.items() if len(paths) > 1}
    if not size_candidates:
        return []

    # Stage 2: Prefix hashing (Quick 8KB check)
    prefix_candidates: dict[tuple[int, str], list[str]] = {}

    def _process_prefix(item: tuple[int, str]) -> tuple[int, str, str | None]:
        size, path = item
        if stop_event is not None and stop_event.is_set():
            return size, path, None
        return size, path, _hash_prefix(path)

    all_size_items = [(size, path) for size, paths in size_candidates.items() for path in paths]

    workers = min(max_workers, len(all_size_items))
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for size, path, p_hash in pool.map(_process_prefix, all_size_items):
                if stop_event is not None and stop_event.is_set():
                    return []
                if p_hash is not None:
                    prefix_candidates.setdefault((size, p_hash), []).append(path)
    else:
        for size, path in all_size_items:
            if stop_event is not None and stop_event.is_set():
                return []
            p_hash = _hash_prefix(path)
            if p_hash is not None:
                prefix_candidates.setdefault((size, p_hash), []).append(path)

    # Filter to only matching prefix groups with 2 or more files
    matching_prefix_groups = {k: paths for k, paths in prefix_candidates.items() if len(paths) > 1}
    if not matching_prefix_groups:
        return []

    # Stage 3: Full SHA-256 checksum for candidate duplicates
    by_full_hash: dict[tuple[int, str], list[str]] = {}
    processed = 0
    total_candidates = sum(len(paths) for paths in matching_prefix_groups.values())

    for (size, _), paths in matching_prefix_groups.items():
        if size <= _PREFIX_SIZE:
            # Files smaller than or equal to prefix size are already fully verified!
            by_full_hash.setdefault((size, _), []).extend(paths)
            processed += len(paths)
            if progress_cb is not None:
                progress_cb(processed, total_candidates)
            continue

        for path in paths:
            if stop_event is not None and stop_event.is_set():
                return []
            full_digest = _hash_full_file(path)
            processed += 1
            if full_digest:
                by_full_hash.setdefault((size, full_digest), []).append(path)
            if progress_cb is not None and processed % 20 == 0:
                progress_cb(processed, total_candidates)

    groups = [
        DuplicateGroup(size=size, files=paths)
        for (size, _digest), paths in by_full_hash.items()
        if len(paths) > 1
    ]
    groups.sort(key=lambda g: g.reclaimable, reverse=True)
    return groups
