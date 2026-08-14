"""Tests for history store."""

from datetime import datetime

from crapcleaner.history.store import append, clear, load
from crapcleaner.models.history import HistoryEntry


class TestHistory:
    def test_append_and_load(self):
        clear()
        entry = HistoryEntry(
            kind="scan",
            started=datetime(2024, 1, 1, 12, 0),
            duration=1.5,
            total_identified=4096,
        )
        append(entry)
        entries = load()
        assert len(entries) == 1
        assert entries[0].kind == "scan"
        assert entries[0].total_identified == 4096
        assert entries[0].started == datetime(2024, 1, 1, 12, 0)

    def test_limit(self):
        clear()
        for i in range(10):
            append(HistoryEntry(kind="scan", started=datetime.now(), duration=float(i)))
        entries = load(limit=3)
        assert len(entries) == 3

    def test_clear(self):
        append(HistoryEntry(kind="scan", started=datetime.now()))
        clear()
        assert load() == []

    def test_missing_file(self):
        clear()
        assert load() == []
