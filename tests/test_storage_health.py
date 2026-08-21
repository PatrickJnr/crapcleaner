"""Unit tests for storage health and TRIM diagnostics."""

import json
from unittest.mock import patch

from crapcleaner.system.storage_health import (
    DiskHealthInfo,
    _get_fallback_storage_health,
    _get_windows_trim_status,
    get_storage_health_report,
)


def _fsutil(stdout):
    return patch("crapcleaner.system.storage_health.run_command", return_value={"stdout": stdout})


def test_get_windows_trim_status():
    with _fsutil("NTFS DisableDeleteNotify = 0 (Disabled)\nReFS DisableDeleteNotify = 0"):
        assert _get_windows_trim_status("NTFS") == (True, True)

    with _fsutil("NTFS DisableDeleteNotify = 1 (Enabled)"):
        assert _get_windows_trim_status("NTFS") == (True, False)

    # Pre-8.1 fsutil printed a single unnamed row that answers for every volume.
    with _fsutil("DisableDeleteNotify = 0"):
        assert _get_windows_trim_status("NTFS") == (True, True)


def test_windows_trim_is_reported_per_filesystem():
    """XP-01: NTFS off with ReFS on must not read as TRIM enabled everywhere."""
    with _fsutil("NTFS DisableDeleteNotify = 1\nReFS DisableDeleteNotify = 0"):
        assert _get_windows_trim_status("NTFS") == (True, False)
        assert _get_windows_trim_status("ReFS") == (True, True)
        assert _get_windows_trim_status("exFAT") == (None, None)

    with _fsutil(""):
        assert _get_windows_trim_status("NTFS") == (None, None)


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
    assert report[0].health_status == "Unknown"


def _disk(device_id="C:"):
    from crapcleaner.system.storage_health import DiskHealthInfo

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
    from crapcleaner.system import storage_health

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
    from crapcleaner.system import storage_health

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


_LSBLK_DEVICE = {
    "name": "nvme0n1",
    "model": "Some NVMe",
    "rota": False,
    "size": "512110190592",
    "type": "disk",
    "tran": "nvme",
    "fstype": None,
    "mountpoint": None,
    "disc-gran": "512",
}


def _linux_disks(monkeypatch, *, disc_gran="512", tools=(), mount_options=(), trim_timer=""):
    """One lsblk device, with only `tools` on PATH."""
    from crapcleaner.system import storage_health

    device = dict(_LSBLK_DEVICE, **{"disc-gran": disc_gran})
    payload = json.dumps({"blockdevices": [device]})

    def fake_run(args, **_kwargs):
        if args[0] == "lsblk":
            return {"stdout": payload, "returncode": 0}
        if args[0] == "systemctl":
            return {"stdout": trim_timer, "returncode": 0}
        return {"stdout": "", "returncode": 0}

    monkeypatch.setattr(storage_health, "run_command", fake_run)
    monkeypatch.setattr(
        storage_health.shutil, "which", lambda t: f"/usr/bin/{t}" if t in tools else None
    )
    monkeypatch.setattr(storage_health, "_mount_options", lambda _d: set(mount_options))
    return storage_health._get_linux_storage_health()


def test_linux_health_is_unknown_when_nothing_can_measure_it(monkeypatch):
    """XP-02: lsblk cannot report health, so a drive must not be declared Healthy."""
    disks = _linux_disks(monkeypatch)
    assert len(disks) == 1
    assert disks[0].health_status == "Unknown"
    assert disks[0].operational_status == "Unknown"


def test_linux_health_comes_from_smartctl_when_it_is_installed(monkeypatch):
    from crapcleaner.system import storage_health

    monkeypatch.setattr(storage_health.shutil, "which", lambda _t: "/usr/sbin/smartctl")
    monkeypatch.setattr(
        storage_health,
        "run_command",
        lambda *_a, **_k: {"stdout": json.dumps({"smart_status": {"passed": False}})},
    )
    assert storage_health._smart_health("/dev/nvme0n1") == (
        "Unhealthy",
        "SMART self-assessment failed",
    )


def test_linux_trim_support_comes_from_discard_granularity(monkeypatch):
    """XP-02: an SSD whose queue reports no discard support must not claim TRIM."""
    disks = _linux_disks(monkeypatch, disc_gran="0")
    assert disks[0].trim_supported is False
    assert disks[0].trim_enabled is False

    disks = _linux_disks(monkeypatch, disc_gran=None)
    assert disks[0].trim_supported is None
    assert disks[0].trim_enabled is None


def test_linux_trim_enabled_needs_discard_or_the_fstrim_timer(monkeypatch):
    assert _linux_disks(monkeypatch, mount_options=("rw", "discard"))[0].trim_enabled is True

    disks = _linux_disks(monkeypatch, tools=("systemctl",), trim_timer="enabled")
    assert disks[0].trim_supported is True
    assert disks[0].trim_enabled is True

    disks = _linux_disks(monkeypatch, tools=("systemctl",), trim_timer="disabled")
    assert disks[0].trim_enabled is False

    # No systemd to ask: discard is supported, but whether it ever runs is unknowable.
    assert _linux_disks(monkeypatch)[0].trim_enabled is None


def test_a_withheld_reliability_counter_reads_as_unknown_not_zero():
    """Get-StorageReliabilityCounter needs elevation; a missing reading is not a healthy 0."""
    from crapcleaner.system.storage_health import _as_counter

    assert _as_counter(None) is None
    assert _as_counter("") is None
    assert _as_counter("not-a-number") is None
    assert _as_counter(0) == 0
    assert _as_counter("41") == 41


def test_disk_health_serialises_its_reliability_counters():
    from crapcleaner.system.storage_health import DiskHealthInfo

    disk = DiskHealthInfo(
        device_id="C:",
        model="WD_BLACK SN770",
        media_type="NVMe SSD",
        bus_type="NVMe",
        capacity=1000,
        free_space=500,
        filesystem="NTFS",
        trim_supported=True,
        trim_enabled=True,
        health_status="Healthy",
        operational_status="OK",
        temperature_c=41,
        wear_percent=3,
    )
    data = disk.to_dict()

    assert data["temperature_c"] == 41
    assert data["wear_percent"] == 3
    # Counters this drive did not report must survive the round trip as unknown.
    assert data["power_on_hours"] is None
    assert data["read_errors"] is None


def test_a_zero_lifetime_also_bypasses_the_stored_report():
    """ttl=0 means "read it fresh", which the persistent layer must not quietly override."""
    from unittest.mock import patch

    from crapcleaner.system import storage_health as sh

    sample = [
        sh.DiskHealthInfo(
            device_id="C:",
            model="WD",
            media_type="SSD",
            bus_type="NVMe",
            capacity=10,
            free_space=5,
            filesystem="NTFS",
            trim_supported=True,
            trim_enabled=True,
            health_status="Healthy",
            operational_status="OK",
        )
    ]
    with patch.object(sh, "list_drives", return_value=["C:"]):
        with patch.object(sh, "get_drive_info", return_value={"total": 10, "free": 5}):
            with patch.object(sh, "_query_storage_health", return_value=sample) as query:
                sh.clear_storage_health_cache()
                sh.get_storage_health_report()
                sh._cached_report = None
                sh.get_storage_health_report(ttl=0)

    assert query.call_count == 2
