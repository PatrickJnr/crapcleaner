"""Local history store (JSONL append-only log of scans and cleanups)."""

import json
import os
import threading

from crapcleaner.config import config_dir
from crapcleaner.constants import HISTORY_FILE
from crapcleaner.models.history import HistoryEntry

_lock = threading.Lock()


def history_path() -> str:
    return os.path.join(config_dir(), HISTORY_FILE)


def append(entry: HistoryEntry) -> None:
    with _lock:
        os.makedirs(config_dir(), exist_ok=True)
        with open(history_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")


def load(limit: int = 200) -> list[HistoryEntry]:
    path = history_path()
    entries: list[HistoryEntry] = []
    if not os.path.exists(path):
        return entries
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return entries
    for line in lines[-limit:]:
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
