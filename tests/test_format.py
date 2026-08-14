"""Tests for format helpers."""

from datetime import datetime

from crapcleaner.utils.format import (
    bytes_from_mtime,
    format_datetime,
    format_duration,
    format_size,
    parse_size,
)


class TestFormatSize:
    def test_bytes(self):
        assert format_size(0) == "0 B"
        assert format_size(512) == "512 B"

    def test_kb(self):
        assert format_size(2048) == "2.0 KB"

    def test_mb(self):
        assert format_size(5 * 1024 * 1024) == "5.0 MB"

    def test_gb(self):
        assert format_size(3 * 1024**3) == "3.0 GB"

    def test_decimals(self):
        assert format_size(1536, decimals=0) == "2 KB"

    def test_none(self):
        assert format_size(None) == "0 B"


class TestParseSize:
    def test_bare_bytes(self):
        assert parse_size("100") == 100

    def test_b(self):
        assert parse_size("100 B") == 100

    def test_kb(self):
        assert parse_size("1KB") == 1024

    def test_mb(self):
        assert parse_size("1 MB") == 1024**2

    def test_gb(self):
        assert parse_size("1GB") == 1024**3

    def test_tb(self):
        assert parse_size("1 TB") == 1024**4

    def test_lowercase(self):
        assert parse_size("2kb") == 2048

    def test_decimal(self):
        assert parse_size("1.5 MB") == int(1.5 * 1024**2)

    def test_invalid(self):
        import pytest

        with pytest.raises(ValueError):
            parse_size("abc")


class TestFormatDuration:
    def test_seconds(self):
        assert format_duration(5) == "5.0s"

    def test_minutes(self):
        assert format_duration(90) == "1m 30s"

    def test_hours(self):
        assert format_duration(3660) == "1h 1m"


class TestFormatDatetime:
    def test_none(self):
        assert format_datetime(None) == "Never"

    def test_value(self):
        dt = datetime(2024, 1, 2, 3, 4)
        assert format_datetime(dt) == "2024-01-02 03:04"


class TestBytesFromMtime:
    def test_roundtrip(self):
        import time

        ts = time.time()
        dt = bytes_from_mtime(ts)
        assert int(dt.timestamp()) == int(ts)
