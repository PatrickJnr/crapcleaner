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

    Only qualifying files take the lock, so the common case costs one comparison.
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

    collector = OldFileCollector(min_age_days, min_size_bytes, max_results)
    try:
        for _dirpath, file_entries in walk_safe_entries(root_path):
            if stop_event is not None and stop_event.is_set():
                break
            for entry in file_entries:
                try:
                    st = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                collector.observe(entry.path, entry.name, st)
    except OSError:
        pass
    return collector.results()
