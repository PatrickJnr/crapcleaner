"""Tests for the physical-disk drive inventory and its maintenance actions."""

import json
from contextlib import contextmanager
from unittest.mock import patch

from crapcleaner.system import drive_actions, drives
from crapcleaner.system.drives import (
    UNMAPPED_DISK_NUMBER,
    PhysicalDiskInfo,
    VolumeInfo,
    clear_drives_cache,
    get_drives_report,
)

# One NVMe SSD reporting reliability counters, one HDD withholding them.
_SAMPLE_DISKS = [
    {
        "DiskNumber": 0,
        "Model": "WD_BLACK SN770 1TB",
        "MediaType": "SSD",
        "BusType": "NVMe",
        "Size": 999167094784,
        "HealthStatus": "Healthy",
        "OperationalStatus": "OK",
        "Temperature": 41,
        "Wear": 3,
        "PowerOnHours": 1204,
        "StartStopCycles": 88,
        "ReadErrors": 0,
        "WriteErrors": 0,
        "Volumes": [
            {
                "Letter": "C:",
                "Label": "",
                "FileSystem": "NTFS",
                "Capacity": 999167094784,
                "Free": 129954340864,
            }
        ],
    },
    {
        "DiskNumber": 2,
        "Model": "ST2000DM006-2DM164",
        "MediaType": "HDD",
        "BusType": "SATA",
        "Size": 1999469801472,
        "HealthStatus": "Healthy",
        "OperationalStatus": "OK",
        "Temperature": None,
        "Wear": None,
        "PowerOnHours": None,
        "StartStopCycles": None,
        "ReadErrors": None,
        "WriteErrors": None,
        "Volumes": [
            {
                "Letter": "T:",
                "Label": "Another Drive",
                "FileSystem": "NTFS",
                "Capacity": 1999469801472,
                "Free": 1138212331520,
            }
        ],
    },
]


def _run_drives_query(sample=None, health=()):
    """Build a drives report from canned PowerShell output."""
    payload = json.dumps(_SAMPLE_DISKS if sample is None else sample)
    with patch.object(drives, "is_windows", return_value=True):
        with patch.object(drives, "run_command", return_value={"stdout": payload}):
            with patch.object(drives, "_windows_trim_states", return_value={"NTFS": True}):
                with patch.object(drives, "get_storage_health_report", return_value=list(health)):
                    clear_drives_cache()
                    return get_drives_report(force_refresh=True)


def test_volumes_nest_under_their_physical_disk():
    report = _run_drives_query()

    assert [d.disk_number for d in report] == [0, 2]
    assert [v.letter for v in report[0].volumes] == ["C:"]
    assert [v.letter for v in report[1].volumes] == ["T:"]
    assert report[1].volumes[0].label == "Another Drive"


def test_an_nvme_ssd_is_not_labelled_a_plain_ssd():
    """Windows reports NVMe drives as MediaType 'SSD'; only the bus distinguishes them."""
    report = _run_drives_query()

    assert report[0].media_type == "NVMe SSD"
    assert report[1].media_type == "HDD"


def test_trim_applies_to_solid_state_volumes_only():
    report = _run_drives_query()

    assert report[0].volumes[0].trim_enabled is True
    # A spinning disk has no TRIM to enable, so reporting it as available would mislead.
    assert report[1].volumes[0].trim_enabled is False


def test_a_withheld_counter_is_unknown_rather_than_zero():
    """Counters need elevation. Reporting 0 hours on a used drive would be a lie."""
    report = _run_drives_query()

    assert report[0].temperature_c == 41
    assert report[0].has_telemetry is True
    assert report[1].power_on_hours is None
    assert report[1].has_telemetry is False


def test_fragmentation_is_not_measured_during_an_inventory():
    """Analysis needs elevation and real time, so a page load must not trigger it."""
    report = _run_drives_query()

    assert all(v.fragmentation_percent is None for d in report for v in d.volumes)
    assert all(v.defrag_verdict is None for d in report for v in d.volumes)


def test_a_volume_with_no_physical_disk_still_appears():
    """Explorer shows mapped and virtual drives; dropping them would disagree with it."""

    class _Stray:
        device_id = "G:"
        model = "Google Drive"
        media_type = "Unknown"
        bus_type = "Unknown"
        capacity = 999167094784
        free_space = 123456622592
        filesystem = "FAT32"
        trim_supported = None
        trim_enabled = None
        health_status = "Unknown"
        operational_status = "Unknown"
        temperature_c = None
        wear_percent = None
        power_on_hours = None
        start_stop_cycles = None
        read_errors = None
        write_errors = None

    report = _run_drives_query(health=[_Stray()])

    stray_group = report[-1]
    assert stray_group.disk_number == UNMAPPED_DISK_NUMBER
    assert stray_group.is_unmapped is True
    assert [v.letter for v in stray_group.volumes] == ["G:"]


def test_a_volume_already_on_a_disk_is_not_duplicated_into_the_stray_group():
    class _Mapped:
        device_id = "C:"
        model = "WD_BLACK SN770 1TB"
        media_type = "NVMe SSD"
        bus_type = "NVMe"
        capacity = 999167094784
        free_space = 129954340864
        filesystem = "NTFS"
        trim_supported = True
        trim_enabled = True
        health_status = "Healthy"
        operational_status = "OK"
        temperature_c = None
        wear_percent = None
        power_on_hours = None
        start_stop_cycles = None
        read_errors = None
        write_errors = None

    report = _run_drives_query(health=[_Mapped()])

    assert all(not d.is_unmapped for d in report)


def test_unreadable_query_output_does_not_raise():
    with patch.object(drives, "is_windows", return_value=True):
        with patch.object(drives, "run_command", return_value={"stdout": "not json"}):
            with patch.object(drives, "get_storage_health_report", return_value=[]):
                clear_drives_cache()
                assert get_drives_report(force_refresh=True) == []


def test_the_inventory_is_cached_between_reads():
    calls = []

    def counting_query():
        calls.append(1)
        return [PhysicalDiskInfo(disk_number=0, volumes=[VolumeInfo(letter="C:")])]

    with patch.object(drives, "_query_drives", side_effect=counting_query):
        clear_drives_cache()
        get_drives_report()
        get_drives_report()
        assert len(calls) == 1

        get_drives_report(force_refresh=True)
        assert len(calls) == 2


def test_callers_cannot_mutate_the_cached_inventory():
    with patch.object(
        drives,
        "_query_drives",
        return_value=[PhysicalDiskInfo(disk_number=0)],
    ):
        clear_drives_cache()
        first = get_drives_report()
        first.append(PhysicalDiskInfo(disk_number=9))

        assert len(get_drives_report()) == 1


def test_disk_and_volume_serialise():
    disk = PhysicalDiskInfo(
        disk_number=0,
        model="WD_BLACK SN770 1TB",
        temperature_c=41,
        volumes=[VolumeInfo(letter="C:", filesystem="NTFS")],
    )
    data = disk.to_dict()

    assert data["temperature_c"] == 41
    assert data["wear_percent"] is None
    assert data["volumes"][0]["letter"] == "C:"


# --- actions -----------------------------------------------------------------


def test_only_a_real_drive_letter_reaches_a_command():
    """The letter lands in a WMI filter and a command line, so it is validated, not escaped."""
    for hostile in ("CC", "", "C: & calc", "../x", "C:;shutdown"):
        assert drive_actions._normalise_letter(hostile) is None

    assert drive_actions._normalise_letter("c:") == "C"
    assert drive_actions._normalise_letter("D:\\") == "D"


def test_a_bad_letter_is_refused_before_running_anything():
    with patch.object(drive_actions, "run_command") as run:
        ok, message, percent = drive_actions.analyze_volume("C: & calc")

    assert ok is False
    assert percent is None
    assert "not a drive letter" in message
    run.assert_not_called()


def test_both_actions_refuse_without_elevation_and_run_nothing():
    with patch.object(drive_actions, "is_windows", return_value=True):
        with patch.object(drive_actions, "is_admin", return_value=False):
            with patch.object(drive_actions, "run_command") as run:
                analyzed = drive_actions.analyze_volume("C")
                optimized = drive_actions.optimize_volume("C")

    assert analyzed[0] is False and optimized[0] is False
    assert "Administrator" in analyzed[1] and "Administrator" in optimized[1]
    run.assert_not_called()


def _elevated_windows():
    return (
        patch.object(drive_actions, "is_windows", return_value=True),
        patch.object(drive_actions, "is_admin", return_value=True),
    )


def test_a_successful_analysis_reports_the_fragmentation_percentage():
    payload = json.dumps(
        {"ReturnValue": 0, "DefragRecommended": True, "TotalPercent": 17, "FilePercent": 12}
    )
    win, admin = _elevated_windows()
    with win, admin:
        with patch.object(drive_actions, "run_command", return_value={"stdout": payload}):
            ok, message, percent = drive_actions.analyze_volume("D")

    assert ok is True
    assert percent == 17
    assert "17%" in message
    assert "recommends optimising" in message


def test_a_refused_analysis_reports_why_rather_than_a_percentage():
    """DefragAnalysis signals access denial through ReturnValue, not an exception."""
    payload = json.dumps({"ReturnValue": 1, "DefragRecommended": False, "TotalPercent": None})
    win, admin = _elevated_windows()
    with win, admin:
        with patch.object(drive_actions, "run_command", return_value={"stdout": payload}):
            ok, message, percent = drive_actions.analyze_volume("C")

    assert ok is False
    assert percent is None
    assert "Access denied" in message


def test_an_ssd_without_a_percentage_still_gets_a_verdict():
    payload = json.dumps({"ReturnValue": 0, "DefragRecommended": False, "TotalPercent": None})
    win, admin = _elevated_windows()
    with win, admin:
        with patch.object(drive_actions, "run_command", return_value={"stdout": payload}):
            ok, message, percent = drive_actions.analyze_volume("C")

    assert ok is True
    assert percent is None
    assert "does not need optimising" in message


def test_an_out_of_range_percentage_is_discarded():
    payload = json.dumps({"ReturnValue": 0, "DefragRecommended": False, "TotalPercent": 4294967295})
    win, admin = _elevated_windows()
    with win, admin:
        with patch.object(drive_actions, "run_command", return_value={"stdout": payload}):
            ok, _message, percent = drive_actions.analyze_volume("C")

    assert ok is True
    assert percent is None


def test_a_failed_optimisation_is_not_reported_as_success():
    """defrag exits 0 even when it refuses, so the result is read from the output."""
    win, admin = _elevated_windows()
    with win, admin:
        with patch.object(
            drive_actions,
            "run_command",
            return_value={"stdout": "ERROR:Access is denied", "returncode": 0},
        ):
            ok, message = drive_actions.optimize_volume("C")

    assert ok is False
    assert "Access is denied" in message


def test_silent_optimisation_output_is_not_treated_as_success():
    win, admin = _elevated_windows()
    with win, admin:
        with patch.object(
            drive_actions, "run_command", return_value={"stdout": "", "returncode": 0}
        ):
            ok, _message = drive_actions.optimize_volume("C")

    assert ok is False


def test_a_successful_optimisation_reports_the_drive():
    win, admin = _elevated_windows()
    with win, admin:
        with patch.object(drive_actions, "run_command", return_value={"stdout": "OK"}):
            ok, message = drive_actions.optimize_volume("f:")

    assert ok is True
    assert "F:" in message


def test_a_never_run_schedule_is_called_out():
    """267011 is SCHED_S_TASK_HAS_NOT_RUN, and it is invisible everywhere else."""
    payload = json.dumps({"State": "Ready", "LastRun": "04/22/1932", "LastResult": 267011})
    with patch.object(drive_actions, "is_windows", return_value=True):
        with patch.object(drive_actions, "run_command", return_value={"stdout": payload}):
            state, detail = drive_actions.scheduled_optimization_status()

    assert state == "Ready"
    assert "never run" in detail


def test_a_schedule_that_has_run_reports_when():
    payload = json.dumps({"State": "Ready", "LastRun": "2026-08-19 03:00", "LastResult": 0})
    with patch.object(drive_actions, "is_windows", return_value=True):
        with patch.object(drive_actions, "run_command", return_value={"stdout": payload}):
            _state, detail = drive_actions.scheduled_optimization_status()

    assert "2026-08-19" in detail


def test_a_zero_temperature_is_treated_as_no_reading():
    """NVMe controllers answer the counter with zeroes instead of refusing it."""
    from crapcleaner.system.drives import _clean_counters

    disk = PhysicalDiskInfo(disk_number=0, media_type="NVMe SSD", temperature_c=0, wear_percent=3)
    _clean_counters(disk)

    assert disk.temperature_c is None
    # A brand new SSD really can be at 0% wear, so that reading survives.
    assert disk.wear_percent == 3


def test_a_silent_controller_has_its_zero_wear_dropped_too():
    """0 °C with no running hours is a controller answering zeroes, not a pristine drive."""
    from crapcleaner.system.drives import _clean_counters

    disk = PhysicalDiskInfo(
        disk_number=0, media_type="NVMe SSD", temperature_c=0, wear_percent=0, power_on_hours=None
    )
    _clean_counters(disk)

    assert disk.temperature_c is None
    assert disk.wear_percent is None
    assert disk.has_telemetry is False


def test_a_reporting_ssd_keeps_its_zero_wear():
    from crapcleaner.system.drives import _clean_counters

    disk = PhysicalDiskInfo(
        disk_number=0, media_type="NVMe SSD", temperature_c=41, wear_percent=0, power_on_hours=1204
    )
    _clean_counters(disk)

    assert disk.wear_percent == 0
    assert disk.temperature_c == 41


def test_wear_is_dropped_for_a_spinning_disk():
    """Wear is a solid-state concept; 0% on an HDD is noise, not a clean bill of health."""
    from crapcleaner.system.drives import _clean_counters

    disk = PhysicalDiskInfo(disk_number=1, media_type="HDD", temperature_c=28, wear_percent=0)
    _clean_counters(disk)

    assert disk.wear_percent is None
    assert disk.temperature_c == 28


def test_the_inventory_is_reused_until_the_set_of_drives_changes():
    """Probing costs seconds of PowerShell and nothing in it moves while drives stay put."""
    calls = []

    def counting_query():
        calls.append(1)
        return [PhysicalDiskInfo(disk_number=0, volumes=[])]

    with patch.object(drives, "_query_drives", side_effect=counting_query):
        with patch.object(drives, "list_drives", return_value=["C:"]):
            clear_drives_cache()
            get_drives_report()
            get_drives_report()
            assert len(calls) == 1

        # A drive appears: the cached topology no longer describes the machine.
        with patch.object(drives, "list_drives", return_value=["C:", "E:"]):
            get_drives_report()
            assert len(calls) == 2

        # And it is reused again once the new set settles.
        with patch.object(drives, "list_drives", return_value=["C:", "E:"]):
            get_drives_report()
            assert len(calls) == 2


def test_free_space_is_re_read_even_when_the_hardware_is_cached():
    """Capacity and free space move constantly; caching them would show stale numbers."""
    disk = PhysicalDiskInfo(disk_number=0, volumes=[VolumeInfo(letter="C:", free_space=1)])

    with patch.object(drives, "_query_drives", return_value=[disk]):
        with patch.object(drives, "list_drives", return_value=["C:"]):
            clear_drives_cache()
            with patch.object(drives, "get_drive_info", return_value={"total": 100, "free": 10}):
                first = get_drives_report()
            with patch.object(drives, "get_drive_info", return_value={"total": 100, "free": 20}):
                second = get_drives_report()

    assert first[0].volumes[0].free_space == 10
    assert second[0].volumes[0].free_space == 20


def test_refreshing_free_space_does_not_corrupt_the_cached_inventory():
    disk = PhysicalDiskInfo(disk_number=0, volumes=[VolumeInfo(letter="C:", free_space=1)])

    with patch.object(drives, "_query_drives", return_value=[disk]):
        with patch.object(drives, "list_drives", return_value=["C:"]):
            clear_drives_cache()
            with patch.object(drives, "get_drive_info", return_value={"total": 100, "free": 10}):
                report = get_drives_report()
            report[0].volumes[0].fragmentation_percent = 42

            with patch.object(drives, "get_drive_info", return_value={"total": 100, "free": 10}):
                again = get_drives_report()

    assert again[0].volumes[0].fragmentation_percent is None


def test_the_bulk_worker_runs_each_volume_and_reports_totals():
    from crapcleaner.gui.workers import DriveBulkWorker

    seen = []
    results = []

    worker = DriveBulkWorker(["C:", "D:"], "analyze")
    worker.progress.connect(lambda *a: results.append(a))
    worker.done.connect(lambda *a: seen.append(a))

    with patch(
        "crapcleaner.system.drive_actions.analyze_volume",
        side_effect=[(True, "ok", 5), (False, "denied", None)],
    ):
        worker.run()

    assert [r[0] for r in results] == ["C:", "D:"]
    assert seen == [(1, 2)]


def test_a_stopped_bulk_worker_leaves_the_remaining_drives_alone():
    """Stopping between volumes is the only abort Windows offers for an optimisation."""
    from crapcleaner.gui.workers import DriveBulkWorker

    worker = DriveBulkWorker(["C:", "D:", "E:"], "optimize")
    worker.request_stop()

    with patch("crapcleaner.system.drive_actions.optimize_volume") as optimize:
        worker.run()

    optimize.assert_not_called()


# --- linux actions -----------------------------------------------------------

_E4DEFRAG_OUTPUT = """<Fragmented files>                             now/best       size/ext
1. /var/log/syslog                              4/1              4 KB

 Total/best extents                             1234/1100
 Average size per extent                        512 KB
 Fragmentation score                            12
 [0-30 no problem: 31-55 a little bit fragmented: 56- needs defrag]
 This directory (/) does not need defragmentation.
"""


@contextmanager
def _linux(root: bool = True, tools=("fstrim", "e4defrag", "findmnt", "systemctl")):
    def which(name):
        return f"/usr/sbin/{name}" if name in tools else None

    with patch.object(drive_actions, "is_windows", return_value=False):
        with patch.object(drive_actions, "is_admin", return_value=root):
            with patch.object(drive_actions.shutil, "which", side_effect=which):
                with patch.object(drive_actions.os.path, "ismount", return_value=True):
                    yield


def test_a_linux_analysis_reports_the_e4defrag_score():
    with _linux():
        with patch.object(drive_actions, "_linux_fs", return_value="ext4"):
            with patch.object(
                drive_actions, "run_command", return_value={"stdout": _E4DEFRAG_OUTPUT}
            ):
                ok, message, score = drive_actions.analyze_volume("/")

    assert ok is True
    assert score == 12
    assert "fragmentation score 12" in message
    # 12 is inside e4defrag's own 0-30 band, so the verdict must not ask for a defrag.
    assert "No defragmentation needed" in message


def test_a_filesystem_e4defrag_cannot_read_is_refused_rather_than_guessed():
    with _linux():
        with patch.object(drive_actions, "_linux_fs", return_value="btrfs"):
            with patch.object(drive_actions, "run_command") as run:
                ok, message, score = drive_actions.analyze_volume("/data")

    assert ok is False
    assert score is None
    assert "not available for btrfs" in message
    run.assert_not_called()


def test_a_missing_e4defrag_is_reported_not_crashed_on():
    with _linux(tools=("fstrim", "findmnt")):
        with patch.object(drive_actions, "_linux_fs", return_value="ext4"):
            ok, message, score = drive_actions.analyze_volume("/")

    assert ok is False
    assert "e4defrag is not installed" in message


def test_a_linux_optimise_runs_fstrim_and_passes_its_report_through():
    trimmed = "/: 1.2 GiB (1288490188 bytes) trimmed\n"
    with _linux():
        with patch.object(
            drive_actions, "run_command", return_value={"returncode": 0, "stdout": trimmed}
        ) as run:
            ok, message = drive_actions.optimize_volume("/")

    assert ok is True
    assert message == "/: 1.2 GiB (1288490188 bytes) trimmed"
    assert run.call_args[0][0] == ["fstrim", "-v", "/"]


def test_a_failed_fstrim_explains_itself_from_stderr():
    """fstrim distinguishes an unsupported discard from a read-only mount; both matter."""
    with _linux():
        with patch.object(
            drive_actions,
            "run_command",
            return_value={
                "returncode": 32,
                "stdout": "",
                "stderr": "fstrim: /: the discard operation is not supported",
            },
        ):
            ok, message = drive_actions.optimize_volume("/")

    assert ok is False
    assert "discard operation is not supported" in message


def test_linux_actions_refuse_without_root_and_run_nothing():
    with _linux(root=False):
        with patch.object(drive_actions, "_linux_fs", return_value="ext4"):
            with patch.object(drive_actions, "run_command") as run:
                analyzed = drive_actions.analyze_volume("/")
                optimized = drive_actions.optimize_volume("/")

    assert analyzed[0] is False and optimized[0] is False
    assert "Root privileges" in analyzed[1] and "Root privileges" in optimized[1]
    run.assert_not_called()


def test_a_path_that_is_not_a_mount_point_is_refused():
    with _linux():
        with patch.object(drive_actions.os.path, "ismount", return_value=False):
            with patch.object(drive_actions.os.path, "isdir", return_value=False):
                with patch.object(drive_actions, "run_command", return_value={"stdout": ""}):
                    ok, message = drive_actions.optimize_volume("not-a-path")

    assert ok is False
    assert "not a mounted volume" in message


def test_a_device_name_is_resolved_to_the_mount_point_it_serves():
    """The inventory names a Linux volume by device, but fstrim acts on a mount point."""
    with _linux():
        with patch.object(drive_actions.os.path, "ismount", return_value=False):
            with patch.object(
                drive_actions, "run_command", return_value={"returncode": 0, "stdout": "/home\n"}
            ) as run:
                drive_actions.optimize_volume("/dev/sda2")

    assert run.call_args_list[0][0][0][:2] == ["findmnt", "-n"]
    assert run.call_args_list[-1][0][0] == ["fstrim", "-v", "/home"]


def test_the_linux_schedule_reads_the_fstrim_timer():
    def fake_run(args, **kwargs):
        if "is-enabled" in args:
            return {"stdout": "enabled"}
        return {"stdout": "Tue 2026-08-18 00:11:32 UTC"}

    with _linux():
        with patch.object(drive_actions, "run_command", side_effect=fake_run):
            state, detail = drive_actions.scheduled_optimization_status()

    assert state == "Enabled"
    assert "Tue 2026-08-18" in detail


def test_a_timer_that_never_fired_is_the_interesting_case():
    def fake_run(args, **kwargs):
        return {"stdout": "enabled"} if "is-enabled" in args else {"stdout": "n/a"}

    with _linux():
        with patch.object(drive_actions, "run_command", side_effect=fake_run):
            state, detail = drive_actions.scheduled_optimization_status()

    assert state == "Enabled"
    assert "has not run a scheduled TRIM yet" in detail


def test_a_disabled_timer_says_how_to_turn_it_on():
    with _linux():
        with patch.object(drive_actions, "run_command", return_value={"stdout": "disabled"}):
            state, detail = drive_actions.scheduled_optimization_status()

    assert state == "Disabled"
    assert "fstrim.timer" in detail


def test_optimisation_is_unsupported_without_either_tool():
    with _linux(tools=("findmnt",)):
        assert drive_actions.optimisation_supported() is False
    with _linux(tools=("fstrim",)):
        assert drive_actions.optimisation_supported() is True
