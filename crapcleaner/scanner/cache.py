"""Scan result cache: reuse directory sizes and finder output within a TTL.

The cache makes repeated scans (including across app restarts) fast by reusing
prior results instead of re-walking large directory trees. Two kinds of entries
are stored, both keyed by a serialized identity:

* ``dir`` entries - the aggregate ``(total, count, skipped)`` of a
  ``compute_dir_size`` call, keyed by (path, patterns, recurse, only_files,
  max_files).
* ``finder`` entries - the list of paths produced by a category's ``finder``,
  keyed by the finder function name plus its call arguments.

An entry is only reused when every scanned root directory still has the same
(mtime, ctime) pair as when it was recorded AND the entry is younger than the
TTL. Direct additions/removals in a scanned root invalidate it immediately;
deeply nested changes that do not touch a root directory's timestamps are
bounded by the TTL, so results never stay stale for longer than the TTL.

The cache is persisted to JSON under the config directory and written
atomically. It only ever holds display/scan data; cleaning always works from
live disk state.
"""

import json
import os
import threading
import time
from typing import Any

from crapcleaner.config.settings import config_dir

DEFAULT_TTL = 300.0
CACHE_FILE = "scan_cache.json"


def _cache_path() -> str:
    return os.path.join(config_dir(), CACHE_FILE)


def _dir_key(
    path: str,
    patterns: tuple[str, ...],
    recurse: bool,
    only_files: bool,
    max_files: int,
) -> str:
    return json.dumps(
        ["dir", path, list(patterns or ()), recurse, only_files, max_files],
        sort_keys=True,
    )


def _finder_key(finder, args) -> str | None:
    name = getattr(finder, "__name__", None) or repr(finder)
    try:
        return json.dumps(["finder", name, list(args)], sort_keys=True)
    except (TypeError, ValueError):
        return None


def _probe(path: str) -> list[int] | None:
    """Return a cheap change-detection fingerprint for a directory."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return [st.st_mtime_ns, st.st_ctime_ns]


class ScanCache:
    def __init__(self, ttl: float = DEFAULT_TTL, path: str | None = None):
        self._ttl = max(0.0, float(ttl))
        self._path = path or _cache_path()
        self._entries: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._load()

    @property
    def enabled(self) -> bool:
        return self._ttl > 0

    @property
    def stats(self) -> tuple[int, int]:
        """Return (hits, misses) since this cache was created."""
        return self._hits, self._misses

    def _load(self) -> None:
        try:
            with open(self._path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and isinstance(data.get("entries"), dict):
                self._entries = data["entries"]
        except (OSError, ValueError):
            self._entries = {}

    def save(self) -> None:
        if not self._entries:
            return
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            temp = self._path + ".tmp"
            with open(temp, "w", encoding="utf-8") as fh:
                json.dump({"entries": self._entries}, fh)
            os.replace(temp, self._path)
        except OSError:
            pass

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
        try:
            if os.path.exists(self._path):
                os.remove(self._path)
        except OSError:
            pass

    def _fresh(self, entry: dict[str, Any], probes: dict[str, list[int]]) -> bool:
        if not self.enabled:
            return False
        if time.time() - entry.get("cached_at", 0) > self._ttl:
            return False
        for path, expected in probes.items():
            if _probe(path) != expected:
                return False
        return True

    def get_dir(
        self,
        path: str,
        patterns: tuple[str, ...] = (),
        recurse: bool = True,
        only_files: bool = False,
        max_files: int = 200000,
    ) -> tuple[int, int, int] | None:
        key = _dir_key(path, patterns, recurse, only_files, max_files)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None
            if not self._fresh(entry, {path: entry.get("probe", [])}):
                self._misses += 1
                return None
            self._hits += 1
            return entry["total"], entry["count"], entry["skipped"]

    def put_dir(
        self,
        path: str,
        patterns: tuple[str, ...],
        recurse: bool,
        only_files: bool,
        max_files: int,
        total: int,
        count: int,
        skipped: int,
    ) -> None:
        if not self.enabled or not os.path.isdir(path):
            return
        probe = _probe(path)
        if probe is None:
            return
        key = _dir_key(path, patterns, recurse, only_files, max_files)
        with self._lock:
            self._entries[key] = {
                "total": total,
                "count": count,
                "skipped": skipped,
                "probe": probe,
                "cached_at": time.time(),
            }

    def get_finder(self, finder, args) -> list[str] | None:
        if not self.enabled:
            return None
        key = _finder_key(finder, args)
        if key is None:
            return None
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None
            if not self._fresh(entry, entry.get("probes", {})):
                self._misses += 1
                return None
            self._hits += 1
            return list(entry.get("found", []))

    def put_finder(self, finder, args, found: list[str]) -> None:
        if not self.enabled:
            return
        key = _finder_key(finder, args)
        if key is None:
            return
        probes: dict[str, list[int]] = {}
        for group in args or ():
            if not isinstance(group, (list, tuple)):
                continue
            for root in group:
                if isinstance(root, str):
                    probe = _probe(root)
                    if probe is not None:
                        probes[root] = probe
        if not probes:
            return
        with self._lock:
            self._entries[key] = {
                "found": list(found),
                "probes": probes,
                "cached_at": time.time(),
            }
