"""Scan result cache: reuse directory sizes and finder output within a TTL.

Two entry kinds, both keyed by a serialized identity: ``dir`` entries hold the
``(total, count, skipped)`` of a ``compute_dir_size`` call; ``finder`` entries hold
the paths a category's ``finder`` produced.

An entry is reused only while every scanned root still has its recorded
(mtime, ctime) pair AND the entry is younger than the TTL. Nested changes that do
not move a root's timestamps are caught by the TTL alone.

Persisted as JSON under the config directory, written atomically. It holds scan
data only; cleaning always works from live disk state.
"""

import json
import os
import threading
import time
from typing import Any

from crapcleaner.config import config_dir
from crapcleaner.utils.logs import get_logger

logger = get_logger("cache")

DEFAULT_TTL = 300.0
CACHE_FILE = "scan_cache.json"
#: Upper bound on stored entries; past it the oldest are dropped rather than
#: reparsed on every start.
MAX_CACHE_ENTRIES = 5000


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


#: Groups rewritten while the app is open (browser caches, Windows Temp). NTFS
#: updates a directory timestamp lazily, so a change one level below it is missed:
#: these entries get a short life instead of a much costlier deep validity check.
VOLATILE_TTL = 45.0
_VOLATILE_GROUPS = frozenset({"Browsers", "Windows"})


def ttl_for_group(group: str) -> float | None:
    """A shorter TTL for constantly rewritten groups, or None for the default."""
    return VOLATILE_TTL if group in _VOLATILE_GROUPS else None


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

    def _prune(self) -> dict[str, Any]:
        """Entries recent enough to be reusable, bounded in number.

        Without this the file grows without limit and is reparsed on every scan.
        """
        now = time.time()
        keep_age = max(self._ttl * 4, 3600.0)
        fresh = {
            key: entry
            for key, entry in self._entries.items()
            if now - float(entry.get("cached_at", 0)) <= keep_age
        }
        if len(fresh) <= MAX_CACHE_ENTRIES:
            return fresh
        newest = sorted(
            fresh.items(), key=lambda kv: float(kv[1].get("cached_at", 0)), reverse=True
        )
        return dict(newest[:MAX_CACHE_ENTRIES])

    def save(self) -> None:
        with self._lock:
            entries = self._prune()
            self._entries = entries
        try:
            if not entries:
                # Leaving the file behind means every start reparses a cache that
                # pruned to nothing.
                if os.path.exists(self._path):
                    os.remove(self._path)
                return
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            temp = self._path + ".tmp"
            with open(temp, "w", encoding="utf-8") as fh:
                json.dump({"entries": entries}, fh)
            os.replace(temp, self._path)
        except OSError:
            logger.debug("Could not write the scan cache to %s", self._path, exc_info=True)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
        try:
            if os.path.exists(self._path):
                os.remove(self._path)
        except OSError:
            logger.debug("Could not clear the scan cache at %s", self._path, exc_info=True)

    def _fresh(
        self, entry: dict[str, Any], probes: dict[str, list[int]], ttl: float | None = None
    ) -> bool:
        if not self.enabled:
            return False
        max_age = self._ttl if ttl is None else min(self._ttl, ttl)
        if time.time() - entry.get("cached_at", 0) > max_age:
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
        ttl: float | None = None,
    ) -> tuple[int, int, int] | None:
        key = _dir_key(path, patterns, recurse, only_files, max_files)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None
            if not self._fresh(entry, {path: entry.get("probe", [])}, ttl):
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

    def get_finder(self, finder, args, ttl: float | None = None) -> list[str] | None:
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
            if not self._fresh(entry, entry.get("probes", {}), ttl):
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
