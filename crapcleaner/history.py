"""Local history store (JSONL append-only log of scans and cleanups)."""

import json
import os
import threading
from collections import deque

from crapcleaner.config import config_dir
from crapcleaner.constants import HISTORY_FILE
from crapcleaner.models.history import HistoryEntry
from crapcleaner.utils.logs import get_logger

_lock = threading.Lock()

#: Entries kept on disk. Every scan appends one and the view reloads the file after
#: each scan, so without a cap the log grows without limit and is re-read whole.
MAX_ENTRIES = 1000


def history_path() -> str:
    return os.path.join(config_dir(), HISTORY_FILE)


def append(entry: HistoryEntry) -> None:
    with _lock:
        os.makedirs(config_dir(), exist_ok=True)
        path = history_path()
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
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
            data = json.loads(line)
            entries.append(HistoryEntry.from_dict(data))
        except (ValueError, TypeError):
            continue
    return entries


def clear() -> None:
    with _lock:
        try:
            os.remove(history_path())
        except OSError:
            pass
