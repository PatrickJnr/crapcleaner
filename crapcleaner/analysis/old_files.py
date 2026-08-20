"""Old Files Scanner for storage analysis and age-based audit.

Finds files that have not been modified for configurable day thresholds (e.g. 30, 90, 180, 365 days).
Purely read-only analysis; never deletes files automatically.
"""

import heapq
import os
import stat
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from crapcleaner.utils.files import walk_safe_entries


@dataclass
class OldFileInfo:
    path: str
    name: str
    size: int
    last_modified: datetime
    age_days: int
    extension: str


class OldFileCollector:
    """Keeps the oldest files it is shown, from any number of threads.

    Only files that already qualify take the lock, so the common case - a file that
    is not old enough - costs one comparison on the scanning thread.
    """

    __slots__ = ("_cutoff", "_min_size", "_max_results", "_heap", "_lock", "_seen", "_now")

    def __init__(
        self, min_age_days: int = 90, min_size_bytes: int = 0, max_results: int = 1000
    ) -> None:
        self._now = time.time()
        self._cutoff = self._now - (min_age_days * 86400)
        self._min_size = min_size_bytes
        self._max_results = max_results
        self._heap: list[tuple[float, int, OldFileInfo]] = []
        self._lock = threading.Lock()
        self._seen = 0

    def observe(self, path: str, name: str, st) -> None:
        if st.st_mtime > self._cutoff or st.st_size < self._min_size:
            return
        if not stat.S_ISREG(st.st_mode) or stat.S_ISLNK(st.st_mode):
            return
        info = OldFileInfo(
            path=path,
            name=name,
            size=st.st_size,
            last_modified=datetime.fromtimestamp(st.st_mtime),
            age_days=int((self._now - st.st_mtime) / 86400),
            extension=Path(name).suffix.lower().lstrip(".") or "unknown",
        )
        with self._lock:
            self._seen += 1
            candidate = (-st.st_mtime, self._seen, info)
            if self._max_results <= 0:
                self._heap.append(candidate)
            elif len(self._heap) < self._max_results:
                heapq.heappush(self._heap, candidate)
            elif candidate[0] > self._heap[0][0]:
                heapq.heapreplace(self._heap, candidate)

    def results(self) -> list[OldFileInfo]:
        with self._lock:
            found = [info for _neg_mtime, _order, info in self._heap]
        found.sort(key=lambda item: item.last_modified)
        return found


def find_old_files(
    root_path: str,
    min_age_days: int = 90,
    min_size_bytes: int = 0,
    max_results: int = 1000,
    stop_event=None,
) -> list[OldFileInfo]:
    """Scan root_path and return files older than min_age_days without modification."""
    if not root_path or not os.path.exists(root_path):
        return []

    now_ts = time.time()
    cutoff_ts = now_ts - (min_age_days * 86400)

    # A bounded heap, not "the first N found". Stopping the walk at `max_results` and
    # sorting afterwards returned whichever files the traversal reached first in
    # directory order, under a heading that says these are the oldest files.
    # `-mtime` so the heap's root is the newest kept entry, which is the one a newly
    # seen older file should displace.
    heap: list[tuple[float, int, OldFileInfo]] = []
    seen = 0

    try:
        for dirpath, file_entries in walk_safe_entries(root_path):
            if stop_event is not None and stop_event.is_set():
                break

            for entry in file_entries:
                try:
                    st = entry.stat(follow_symlinks=False)
                except OSError:
                    continue

                if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
                    continue

                mtime = st.st_mtime
                if mtime > cutoff_ts or st.st_size < min_size_bytes:
                    continue

                seen += 1
                info = OldFileInfo(
                    path=entry.path,
                    name=entry.name,
                    size=st.st_size,
                    last_modified=datetime.fromtimestamp(mtime),
                    age_days=int((now_ts - mtime) / 86400),
                    extension=Path(entry.name).suffix.lower().lstrip(".") or "unknown",
                )
                candidate = (-mtime, seen, info)
                if max_results <= 0:
                    heap.append(candidate)
                elif len(heap) < max_results:
                    heapq.heappush(heap, candidate)
                elif candidate[0] > heap[0][0]:
                    heapq.heapreplace(heap, candidate)
    except OSError:
        pass

    results = [info for _neg_mtime, _order, info in heap]
    results.sort(key=lambda x: x.last_modified)
    return results
