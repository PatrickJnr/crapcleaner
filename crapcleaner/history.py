"""Local history store (JSONL append-only log of scans and cleanups)."""

import json
import os
import threading
from collections import deque
from dataclasses import fields
from datetime import datetime

from crapcleaner.config import config_dir
from crapcleaner.constants import HISTORY_FILE
from crapcleaner.models.history import HistoryEntry
from crapcleaner.utils.logs import get_logger

_lock = threading.Lock()

#: Entries kept on disk. Every scan appends one and the view reloads the file after
#: each scan, so without a cap the log grows without limit and is re-read whole.
MAX_ENTRIES = 1000

#: Per-run detail the model may not carry yet. Written and read by name so a build
#: whose HistoryEntry predates them still round-trips a log written by one that has.
_EXTRA_FIELDS = ("category_sizes", "manifest_path")

#: Runs regrowth_estimate averages over: enough to smooth a one-off spike without
#: reaching back to a machine that has since changed.
_REGROWTH_RUNS = 5
_WEEK_SECONDS = 7 * 24 * 3600.0


def history_path() -> str:
    return os.path.join(config_dir(), HISTORY_FILE)


def append(entry: HistoryEntry) -> None:
    data = entry.to_dict()
    for name in _EXTRA_FIELDS:
        value = getattr(entry, name, None)
        if name not in data and value is not None:
            data[name] = value
    with _lock:
        os.makedirs(config_dir(), exist_ok=True)
        path = history_path()
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(data, ensure_ascii=False, default=str) + "\n")
        _trim_locked(path)


def _trim_locked(path: str) -> None:
    """Keep the newest MAX_ENTRIES lines. Caller holds the lock.

    Rewritten through a temporary file so an interrupted trim cannot truncate the
    history it was tidying.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            tail = deque(fh, maxlen=MAX_ENTRIES)
            if fh.tell() and len(tail) < MAX_ENTRIES:
                return
    except OSError:
        return

    try:
        with open(path, encoding="utf-8") as fh:
            total = sum(1 for _ in fh)
        if total <= MAX_ENTRIES:
            return
        temp = path + ".tmp"
        with open(temp, "w", encoding="utf-8") as fh:
            fh.writelines(tail)
        os.replace(temp, path)
    except OSError:
        get_logger("history").debug("Could not trim the history log", exc_info=True)


def load(limit: int = 200) -> list[HistoryEntry]:
    path = history_path()
    entries: list[HistoryEntry] = []
    if not os.path.exists(path):
        return entries
    try:
        with open(path, encoding="utf-8") as fh:
            # deque keeps only the tail in memory rather than the whole file.
            lines = deque(fh, maxlen=max(1, limit))
    except OSError:
        return entries
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(_from_dict(json.loads(line)))
        except (ValueError, TypeError):
            continue
    return entries


def _from_dict(data: dict) -> HistoryEntry:
    """Build an entry, keeping keys this build's model has no field for."""
    known = {f.name for f in fields(HistoryEntry)}
    entry = HistoryEntry.from_dict({k: v for k, v in data.items() if k in known})
    for key in _EXTRA_FIELDS:
        if key not in known and key in data:
            setattr(entry, key, data[key])
    return entry


def _category_sizes(entry: HistoryEntry) -> dict[str, int]:
    sizes = getattr(entry, "category_sizes", None)
    return sizes if isinstance(sizes, dict) else {}


def last_cleaned(category_id: str) -> datetime | None:
    """When this category was last really cleaned, or None if it never was."""
    for entry in reversed(load(limit=MAX_ENTRIES)):
        if entry.kind != "cleanup" or entry.dry_run:
            continue
        if category_id in _category_sizes(entry) or category_id in entry.categories:
            return entry.started
    return None


def regrowth_estimate(category_id: str) -> float | None:
    """Bytes this category grows back per week, or None without enough history.

    What a run reclaimed is what accumulated since the run before it, so the oldest
    run in the window only supplies the start of the clock.
    """
    runs = [
        (entry.started, int(_category_sizes(entry)[category_id]))
        for entry in load(limit=MAX_ENTRIES)
        if entry.kind == "cleanup" and not entry.dry_run and category_id in _category_sizes(entry)
    ][-_REGROWTH_RUNS:]
    if len(runs) < 2:
        return None
    span = (runs[-1][0] - runs[0][0]).total_seconds()
    if span <= 0:
        return None
    return sum(size for _, size in runs[1:]) * _WEEK_SECONDS / span


def clear() -> None:
    with _lock:
        try:
            os.remove(history_path())
        except OSError:
            pass
