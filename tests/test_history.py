"""Tests for history store."""

from datetime import datetime, timedelta

import pytest

from crapcleaner.history import append, clear, last_cleaned, load, regrowth_estimate
from crapcleaner.models.history import HistoryEntry


def _cleanup(started: datetime, sizes: dict | None = None, **kwargs) -> HistoryEntry:
    entry = HistoryEntry(kind="cleanup", started=started, **kwargs)
    if sizes is not None:
        entry.category_sizes = sizes
    return entry


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


class TestPerRunDetail:
    def test_detail_this_build_has_no_field_for_still_round_trips(self):
        clear()
        entry = _cleanup(datetime(2024, 5, 1, 9, 0), {"temp": 2048}, categories=["Temp"])
        entry.manifest_path = "/var/run.json"
        append(entry)

        loaded = load()[0]
        assert getattr(loaded, "category_sizes", None) == {"temp": 2048}
        assert getattr(loaded, "manifest_path", None) == "/var/run.json"

    def test_last_cleaned_ignores_dry_runs(self):
        clear()
        append(_cleanup(datetime(2024, 1, 1), {"temp": 10}))
        append(_cleanup(datetime(2024, 2, 1), {"temp": 10}, dry_run=True))

        assert last_cleaned("temp") == datetime(2024, 1, 1)
        assert last_cleaned("never-cleaned") is None

    def test_regrowth_is_bytes_per_week_between_runs(self):
        clear()
        start = datetime(2024, 1, 1)
        for week, size in enumerate((1000, 400, 600)):
            append(_cleanup(start + timedelta(weeks=week), {"temp": size}))

        assert regrowth_estimate("temp") == pytest.approx(500.0)

    def test_regrowth_needs_two_runs_to_measure_anything(self):
        clear()
        append(_cleanup(datetime(2024, 1, 1), {"temp": 1000}))

        assert regrowth_estimate("temp") is None
