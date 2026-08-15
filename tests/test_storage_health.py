"""Unit tests for storage health and TRIM diagnostics."""

from unittest.mock import patch

from crapcleaner.specs.storage_health import (
    DiskHealthInfo,
    _get_fallback_storage_health,
    _get_windows_trim_status,
    get_storage_health_report,
)


def test_get_windows_trim_status():
    with patch(
        "crapcleaner.specs.storage_health.run_command",
        return_value={
            "stdout": "NTFS DisableDeleteNotify = 0 (Disabled)\nReFS DisableDeleteNotify = 0"
        },
    ):
        supp, enabled = _get_windows_trim_status()
        assert supp is True
        assert enabled is True

    with patch(
        "crapcleaner.specs.storage_health.run_command",
        return_value={"stdout": "NTFS DisableDeleteNotify = 1 (Enabled)"},
    ):
        supp, enabled = _get_windows_trim_status()
        assert supp is True
        assert enabled is False


def test_get_storage_health_report_structure():
    report = get_storage_health_report()
    assert isinstance(report, list)
    assert len(report) > 0
    for disk in report:
        assert isinstance(disk, DiskHealthInfo)
        d = disk.to_dict()
        assert "device_id" in d
        assert "media_type" in d
        assert "health_status" in d


def test_fallback_storage_health():
    report = _get_fallback_storage_health()
    assert len(report) > 0
    assert report[0].health_status == "Healthy"


def _disk(device_id="C:"):
    from crapcleaner.specs.storage_health import DiskHealthInfo

    return DiskHealthInfo(
        device_id=device_id,
        model="Test Disk",
        media_type="SSD",
        bus_type="NVMe",
        capacity=1000,
        free_space=500,
        filesystem="NTFS",
        trim_supported=True,
        trim_enabled=True,
        health_status="Healthy",
        operational_status="OK",
    )


def test_health_report_is_cached_between_calls(monkeypatch):
    from crapcleaner.specs import storage_health

    storage_health.clear_storage_health_cache()
    calls = []

    def fake_query():
        calls.append(1)
        return [_disk()]

    monkeypatch.setattr(storage_health, "_query_storage_health", fake_query)

    first = storage_health.get_storage_health_report()
    second = storage_health.get_storage_health_report()
    assert len(calls) == 1
    assert [d.device_id for d in first] == [d.device_id for d in second]

    storage_health.get_storage_health_report(force_refresh=True)
    assert len(calls) == 2

    storage_health.get_storage_health_report(ttl=0)
    assert len(calls) == 3

    storage_health.clear_storage_health_cache()
    storage_health.get_storage_health_report()
    assert len(calls) == 4


def test_cached_report_is_a_copy(monkeypatch):
    from crapcleaner.specs import storage_health

    storage_health.clear_storage_health_cache()
    monkeypatch.setattr(
        storage_health,
        "_query_storage_health",
        lambda: [_disk()],
    )
    first = storage_health.get_storage_health_report()
    first.clear()
    assert len(storage_health.get_storage_health_report()) == 1
    storage_health.clear_storage_health_cache()
