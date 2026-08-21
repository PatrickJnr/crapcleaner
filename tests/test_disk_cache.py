"""The probe cache must be fast to read, safe to corrupt, and never serve a stale answer."""

import json
import os
from unittest.mock import patch

from crapcleaner.system import drives, storage_health
from crapcleaner.system.drives import PhysicalDiskInfo, VolumeInfo, get_drives_report
from crapcleaner.utils import disk_cache


def test_a_stored_payload_comes_back():
    disk_cache.store("probe", ["C:"], {"model": "WD_BLACK"})

    assert disk_cache.load("probe", ["C:"]) == {"model": "WD_BLACK"}


def test_a_changed_signature_is_a_miss_not_a_stale_hit():
    """The signature is the whole safety mechanism: no signature match, no answer."""
    disk_cache.store("probe", ["C:"], {"model": "WD_BLACK"})

    assert disk_cache.load("probe", ["C:", "E:"]) is None


def test_a_tuple_signature_survives_the_json_round_trip():
    """JSON has no tuples, so a tuple written must still match when read back."""
    disk_cache.store("probe", list(("C:", "E:")), 1)

    assert disk_cache.load("probe", ["C:", "E:"]) == 1


def test_an_unknown_name_is_a_miss():
    assert disk_cache.load("never-stored", []) is None


def test_a_corrupt_cache_file_is_treated_as_empty():
    """A half-written or hand-edited cache must never stop the app from starting."""
    os.makedirs(os.path.dirname(disk_cache.cache_path()), exist_ok=True)
    with open(disk_cache.cache_path(), "w", encoding="utf-8") as handle:
        handle.write("{not json at all")

    assert disk_cache.load("probe", []) is None
    disk_cache.store("probe", [], 5)
    assert disk_cache.load("probe", []) == 5


def test_a_cache_holding_a_list_instead_of_an_object_is_ignored():
    os.makedirs(os.path.dirname(disk_cache.cache_path()), exist_ok=True)
    with open(disk_cache.cache_path(), "w", encoding="utf-8") as handle:
        json.dump(["unexpected"], handle)

    assert disk_cache.load("probe", []) is None


def test_entries_do_not_overwrite_each_other():
    disk_cache.store("one", [], 1)
    disk_cache.store("two", [], 2)

    assert disk_cache.load("one", []) == 1
    assert disk_cache.load("two", []) == 2


def test_clearing_one_entry_leaves_the_others():
    disk_cache.store("one", [], 1)
    disk_cache.store("two", [], 2)
    disk_cache.clear("one")

    assert disk_cache.load("one", []) is None
    assert disk_cache.load("two", []) == 2


def test_clearing_everything_removes_the_file():
    disk_cache.store("one", [], 1)
    disk_cache.clear()

    assert not os.path.exists(disk_cache.cache_path())
    assert disk_cache.load("one", []) is None


def test_an_unwritable_cache_directory_does_not_raise():
    with patch.object(disk_cache.os, "makedirs", side_effect=OSError("read-only")):
        disk_cache.store("probe", [], 1)

    assert disk_cache.load("probe", []) is None


# --- the probes that use it ---------------------------------------------------


def _one_disk():
    return [
        PhysicalDiskInfo(
            disk_number=0,
            model="WD_BLACK SN770 1TB",
            media_type="NVMe SSD",
            volumes=[VolumeInfo(letter="C:", capacity=100, free_space=40)],
        )
    ]


def test_a_second_launch_reuses_the_inventory_without_probing():
    """Probing costs seconds of PowerShell and the answer is still true next launch."""
    calls = []

    def counting_query():
        calls.append(1)
        return _one_disk()

    with patch.object(drives, "list_drives", return_value=["C:"]):
        with patch.object(drives, "get_drive_info", return_value={"total": 100, "free": 40}):
            with patch.object(drives, "_query_drives", side_effect=counting_query):
                drives.clear_drives_cache()
                first = get_drives_report()

                # A new process starts with an empty in-memory cache but the same file.
                drives._cached_drives = None
                second = get_drives_report()

    assert len(calls) == 1
    assert [d.model for d in first] == [d.model for d in second]
    assert second[0].volumes[0].letter == "C:"


def test_plugging_a_drive_in_invalidates_the_stored_inventory():
    calls = []

    def counting_query():
        calls.append(1)
        return _one_disk()

    with patch.object(drives, "get_drive_info", return_value={"total": 100, "free": 40}):
        with patch.object(drives, "_query_drives", side_effect=counting_query):
            with patch.object(drives, "list_drives", return_value=["C:"]):
                drives.clear_drives_cache()
                get_drives_report()

            drives._cached_drives = None
            with patch.object(drives, "list_drives", return_value=["C:", "E:"]):
                get_drives_report()

    assert len(calls) == 2


def test_free_space_is_re_read_even_on_a_restored_inventory():
    """A cached inventory must never show yesterday's free space."""
    with patch.object(drives, "list_drives", return_value=["C:"]):
        with patch.object(drives, "_query_drives", return_value=_one_disk()):
            with patch.object(drives, "get_drive_info", return_value={"total": 100, "free": 40}):
                drives.clear_drives_cache()
                get_drives_report()

            drives._cached_drives = None
            with patch.object(drives, "get_drive_info", return_value={"total": 100, "free": 90}):
                restored = get_drives_report()

    assert restored[0].volumes[0].free_space == 90


def test_an_inventory_written_by_an_older_model_is_ignored():
    """A cache from a build with different fields is a miss, not a crash."""
    with patch.object(drives, "list_drives", return_value=["C:"]):
        disk_cache.store("drives", ["C:"], [{"disk_number": 0, "gone_field": 1}])
        drives._cached_drives = None

        with patch.object(drives, "_query_drives", return_value=_one_disk()) as query:
            with patch.object(drives, "get_drive_info", return_value={"total": 100, "free": 40}):
                report = get_drives_report()

    query.assert_called_once()
    assert report[0].model == "WD_BLACK SN770 1TB"


def test_an_explicit_refresh_ignores_the_stored_inventory():
    with patch.object(drives, "list_drives", return_value=["C:"]):
        with patch.object(drives, "get_drive_info", return_value={"total": 100, "free": 40}):
            with patch.object(drives, "_query_drives", return_value=_one_disk()) as query:
                drives.clear_drives_cache()
                get_drives_report()
                drives._cached_drives = None
                get_drives_report(force_refresh=True)

    assert query.call_count == 2


def test_storage_health_is_reused_across_launches_but_refreshes_its_free_space():
    sample = [
        storage_health.DiskHealthInfo(
            device_id="C:",
            model="WD_BLACK",
            media_type="NVMe SSD",
            bus_type="NVMe",
            capacity=100,
            free_space=40,
            filesystem="NTFS",
            trim_supported=True,
            trim_enabled=True,
            health_status="Healthy",
            operational_status="OK",
        )
    ]

    with patch.object(storage_health, "list_drives", return_value=["C:"]):
        with patch.object(storage_health, "_query_storage_health", return_value=sample) as query:
            with patch.object(
                storage_health, "get_drive_info", return_value={"total": 100, "free": 40}
            ):
                storage_health.clear_storage_health_cache()
                storage_health.get_storage_health_report()

            storage_health._cached_report = None
            with patch.object(
                storage_health, "get_drive_info", return_value={"total": 100, "free": 75}
            ):
                restored = storage_health.get_storage_health_report()

    query.assert_called_once()
    assert restored[0].model == "WD_BLACK"
    assert restored[0].free_space == 75
