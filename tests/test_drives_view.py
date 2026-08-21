"""The Drives view lists volumes as one scannable table and gates admin-only controls."""

from contextlib import contextmanager
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from crapcleaner.gui.views import drives as drives_view_mod
from crapcleaner.gui.views.drives import _NEEDS_ADMIN, DrivesView
from crapcleaner.system import drives as drives_view_mod_drives
from crapcleaner.system.drives import PhysicalDiskInfo, VolumeInfo

_app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])


def _sample_drives():
    return [
        PhysicalDiskInfo(
            disk_number=0,
            model="WD_BLACK SN770 1TB",
            media_type="NVMe SSD",
            bus_type="NVMe",
            health_status="Healthy",
            temperature_c=41,
            wear_percent=3,
            power_on_hours=1204,
            read_errors=0,
            write_errors=0,
            volumes=[
                VolumeInfo(
                    letter="C:",
                    filesystem="NTFS",
                    capacity=999167094784,
                    free_space=129954340864,
                    trim_supported=True,
                    trim_enabled=True,
                )
            ],
        ),
        PhysicalDiskInfo(
            disk_number=2,
            model="ST2000DM006",
            media_type="HDD",
            bus_type="SATA",
            health_status="Healthy",
            volumes=[
                VolumeInfo(
                    letter="T:",
                    label="Another Drive",
                    filesystem="NTFS",
                    capacity=1999469801472,
                    free_space=1138212331520,
                )
            ],
        ),
    ]


@pytest.fixture(autouse=True)
def _a_windows_machine():
    """Every test here describes a Windows session with the optimisation tools present.

    Patched for the whole test rather than only while the view is built: a test that
    calls into the view afterwards - an analysis result, a confirmation dialog - reads
    the platform again, and would otherwise assert Windows wording against whatever the
    machine running the suite happens to be. The Linux tests override this.
    """
    with patch.object(drives_view_mod, "is_windows", return_value=True):
        with patch.object(drives_view_mod, "can_elevate", return_value=True):
            with patch.object(drives_view_mod, "optimisation_supported", return_value=True):
                yield


@contextmanager
def _running_as(elevated: bool):
    """A Windows session with the optimisation tools available.

    Elevation is re-checked on every repaint, not just at construction, and the
    capability is patched rather than inherited: on a Linux runner it depends on whether
    fstrim happens to be on PATH, which would make these tests pass or fail by accident.
    """
    with patch.object(drives_view_mod, "is_admin", return_value=elevated):
        with patch.object(drives_view_mod, "is_windows", return_value=True):
            with patch.object(drives_view_mod, "optimisation_supported", return_value=True):
                yield


def _build(elevated: bool, drives=None, schedule=("Ready", "")):
    with _running_as(elevated):
        view = DrivesView(main_window=None)
        view._drives = _sample_drives() if drives is None else drives
        view._schedule = schedule
        # What _on_loaded does: the answer has arrived, so the banner stops saying it is
        # still waiting for it.
        view._schedule_pending = False
        view._populate()
        return view


def _row_count(view) -> int:
    """One row per volume; the layout also holds separators and a trailing stretch."""
    return len(view._frag_labels)


def _text_of(view) -> str:
    parts = [c.text() for c in view.findChildren(QLabel)]
    parts += [c.text() for c in view.findChildren(QPushButton)]
    return "\n".join(parts)


def test_every_volume_gets_a_row_naming_the_drive_it_lives_on():
    view = _build(elevated=True)
    text = _text_of(view)

    assert _row_count(view) == 2
    assert "WD_BLACK SN770 1TB" in text
    assert "ST2000DM006" in text
    assert sorted(view._frag_labels) == ["C:", "T:"]


def test_reliability_counters_are_shown_when_the_drive_reports_them():
    view = _build(elevated=True)
    text = _text_of(view)

    assert "Temp  41 °C" in text
    assert "Wear  3 %" in text
    assert "Powered on  1,204 h" in text


def test_a_drive_without_counters_says_so_instead_of_showing_zeroes():
    view = _build(elevated=True)
    text = _text_of(view)

    assert "does not report reliability counters" in text
    assert "0 °C" not in text


def test_unelevated_the_actions_are_disabled_and_explained():
    """Both analysis and optimisation need admin, so offering them would only fail."""
    view = _build(elevated=False)

    buttons = [b for b in view.findChildren(QPushButton) if b.text() in ("Analyse", "Optimise")]
    assert buttons
    assert all(not b.isEnabled() for b in buttons)
    assert all("Relaunch as Admin" in b.toolTip() for b in buttons)
    assert "relaunch as admin" in _text_of(view).lower()


def test_elevated_the_actions_are_available():
    view = _build(elevated=True)

    buttons = [b for b in view.findChildren(QPushButton) if b.text() in ("Analyse", "Optimise")]
    assert buttons
    assert all(b.isEnabled() for b in buttons)


def test_a_schedule_that_never_ran_is_surfaced():
    view = _build(
        elevated=True,
        schedule=("Ready", "Windows has never run its scheduled drive optimisation."),
    )

    assert "never run" in view.status_label.text()


def test_fragmentation_reads_as_unknown_until_measured():
    view = _build(elevated=True)

    assert view._frag_labels["C:"].text() == "—"


def test_a_completed_analysis_updates_the_volume_and_its_label():
    view = _build(elevated=True)
    view._on_analyzed("C:", True, "C: is 17% fragmented.", 17)

    assert view._frag_labels["C:"].text() == "17%"
    assert view._drives[0].volumes[0].fragmentation_percent == 17
    assert "17%" in view.status_label.text()


def test_a_failed_analysis_does_not_invent_a_reading():
    view = _build(elevated=True)
    view._on_analyzed("C:", False, "C: could not be analysed. Access denied.", None)

    assert view._frag_labels["C:"].text() == "—"
    assert view._drives[0].volumes[0].fragmentation_percent is None
    assert "Access denied" in view.status_label.text()


def test_a_virtual_drive_gets_no_row_but_is_accounted_for():
    """Windows cannot optimise a cloud mount, so a row offering to would only mislead."""
    view = _build(
        elevated=True,
        drives=_sample_drives()
        + [
            PhysicalDiskInfo(
                disk_number=-1,
                model="Other volumes",
                media_type="Virtual / Removable",
                volumes=[VolumeInfo(letter="G:", filesystem="FAT32", capacity=10, free_space=5)],
            )
        ],
    )
    text = _text_of(view)

    assert _row_count(view) == 2
    assert "Other volumes" not in text
    assert "G:" not in text
    # Silently dropping a drive the user sees in Explorer would read as a bug.
    assert "1 virtual drive hidden" in view.status_label.text()


def test_no_virtual_drives_means_no_note_about_them():
    view = _build(elevated=True)

    assert "hidden" not in view.status_label.text()


def test_a_declined_optimisation_runs_nothing():
    from PySide6.QtWidgets import QMessageBox

    view = _build(elevated=True)
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
        with patch("crapcleaner.gui.workers.DriveOptimizeWorker") as worker:
            view._optimize(view._drives[0].volumes[0])

    worker.assert_not_called()


def test_the_confirmation_names_the_drive_and_its_size():
    from PySide6.QtWidgets import QMessageBox

    view = _build(elevated=True)
    seen = {}

    def capture(parent, title, text, *args, **kwargs):
        seen["text"] = text
        return QMessageBox.StandardButton.No

    with patch.object(QMessageBox, "question", side_effect=capture):
        view._optimize(view._drives[1].volumes[0])

    assert "T:" in seen["text"]
    # A multi-terabyte defragmentation is a long commitment; the size makes that concrete.
    assert "TB" in seen["text"]
    assert "hours" in seen["text"]


def test_refresh_survives_a_worker_whose_c_side_was_already_deleted():
    """Qt's deleteLater frees the C++ object while the Python reference lingers."""
    import shiboken6

    from crapcleaner.gui.workers import DrivesWorker

    view = _build(elevated=True)

    with patch("crapcleaner.system.drives.get_drives_report", return_value=[]):
        with patch(
            "crapcleaner.system.drive_actions.scheduled_optimization_status",
            return_value=("Ready", ""),
        ):
            view.refresh_drives()
            assert view._worker is not None

            stale = DrivesWorker(parent=view)
            shiboken6.delete(stale)
            view._worker = stale

            view.refresh_drives()
            assert view._worker is not stale
            if view._worker is not None:
                view._worker.wait(2000)

    view.close()


def test_an_elevated_session_says_not_reported_rather_than_needs_admin():
    """Telling an admin they need admin sends them chasing a fix that does not exist."""
    view = _build(
        elevated=True,
        drives=[
            PhysicalDiskInfo(
                disk_number=0,
                model="ST2000DM006",
                media_type="HDD",
                health_status="Healthy",
                temperature_c=28,
                power_on_hours=74559,
                read_errors=0,
                write_errors=None,
                volumes=[VolumeInfo(letter="T:", filesystem="NTFS")],
            )
        ],
    )
    text = _text_of(view)

    # An absent counter is simply left out rather than repeated as non-data.
    assert "Write errors" not in text
    assert "not reported" not in text
    assert "needs admin" not in text
    assert "Temp  28 °C" in text
    assert "Read errors  0" in text


def test_a_drive_that_reports_nothing_says_so_once():
    """Five "not reported" labels in a row is noise pretending to be a reading."""
    view = _build(
        elevated=True,
        drives=[
            PhysicalDiskInfo(
                disk_number=0,
                model="WD_BLACK SN770 1TB",
                media_type="NVMe SSD",
                health_status="Healthy",
                volumes=[VolumeInfo(letter="C:", filesystem="NTFS")],
            )
        ],
    )
    text = _text_of(view)

    assert "does not report reliability counters" in text
    assert text.count("not reported") == 0


def test_an_unelevated_session_still_points_at_elevation():
    view = _build(
        elevated=False,
        drives=[
            PhysicalDiskInfo(
                disk_number=0,
                model="ST2000DM006",
                media_type="HDD",
                write_errors=None,
                volumes=[VolumeInfo(letter="T:", filesystem="NTFS")],
            )
        ],
    )

    assert "needs admin" in _text_of(view)


def test_bulk_buttons_follow_elevation():
    assert _build(elevated=True).analyze_all_btn.isEnabled() is True
    assert _build(elevated=True).optimize_all_btn.isEnabled() is True

    view = _build(elevated=False)
    assert view.analyze_all_btn.isEnabled() is False
    assert view.optimize_all_btn.isEnabled() is False
    assert "Relaunch as Admin" in view.optimize_all_btn.toolTip()


def test_bulk_buttons_stay_disabled_until_drives_load():
    """A sweep over an empty inventory has nothing to do and reads as broken."""
    view = _build(elevated=True, drives=[])

    assert view.analyze_all_btn.isEnabled() is False
    assert view.optimize_all_btn.isEnabled() is False
    assert "No drives loaded yet." in view.analyze_all_btn.toolTip()


def test_bulk_buttons_wake_up_once_the_inventory_arrives():
    view = _build(elevated=True, drives=[])
    assert view.analyze_all_btn.isEnabled() is False

    view._drives = _sample_drives()
    with _running_as(True):
        view._populate()

    assert view.analyze_all_btn.isEnabled() is True
    assert view.optimize_all_btn.toolTip() == ""


def test_a_machine_with_only_virtual_drives_offers_no_sweep():
    view = _build(
        elevated=True,
        drives=[
            PhysicalDiskInfo(
                disk_number=-1,
                model="Other volumes",
                volumes=[VolumeInfo(letter="G:", filesystem="FAT32")],
            )
        ],
    )

    assert view.analyze_all_btn.isEnabled() is False
    assert view.optimize_all_btn.isEnabled() is False


def test_a_bulk_sweep_skips_volumes_with_no_physical_media():
    """A cloud or network mount has nothing to trim or defragment."""
    view = _build(
        elevated=True,
        drives=_sample_drives()
        + [
            PhysicalDiskInfo(
                disk_number=-1,
                model="Other volumes",
                volumes=[VolumeInfo(letter="G:", filesystem="FAT32")],
            )
        ],
    )

    letters = [v.letter for v in view._optimisable_volumes()]
    assert letters == ["C:", "T:"]
    assert "G:" not in letters


def test_analyse_all_queues_every_real_volume():
    view = _build(elevated=True)
    with patch("crapcleaner.gui.workers.DriveBulkWorker") as worker:
        view._analyze_all()

    letters, action = worker.call_args[0][0], worker.call_args[0][1]
    assert letters == ["C:", "T:"]
    assert action == "analyze"
    assert view._frag_labels["C:"].text() == "Queued..."


def test_optimise_all_asks_first_and_names_the_scale():
    from PySide6.QtWidgets import QMessageBox

    view = _build(elevated=True)
    seen = {}

    def capture(parent, title, text, *args, **kwargs):
        seen["text"] = text
        return QMessageBox.StandardButton.No

    with patch.object(QMessageBox, "question", side_effect=capture):
        with patch("crapcleaner.gui.workers.DriveBulkWorker") as worker:
            view._optimize_all()

    worker.assert_not_called()
    assert "C:, T:" in seen["text"]
    assert "2 drives" in seen["text"]
    assert "hours" in seen["text"]


def test_a_running_sweep_turns_its_own_button_into_a_stop():
    view = _build(elevated=True)
    with patch("crapcleaner.gui.workers.DriveBulkWorker"):
        view._analyze_all()

    assert view.analyze_all_btn.text() == "Stop"
    # Nothing else may start while a sweep holds the drives.
    assert view.optimize_all_btn.isEnabled() is False
    assert view.refresh_btn.isEnabled() is False

    with _running_as(True):
        view._on_bulk_done(2, 2)
    assert view.analyze_all_btn.text() == "Analyse All"
    assert view.analyze_all_btn.isEnabled() is True
    assert view.optimize_all_btn.isEnabled() is True
    assert view.refresh_btn.isEnabled() is True


def test_stopping_a_sweep_asks_the_worker_to_stop():
    view = _build(elevated=True)
    with patch("crapcleaner.gui.workers.DriveBulkWorker") as worker_cls:
        view._analyze_all()
        view._stop_bulk()

    worker_cls.return_value.request_stop.assert_called_once()
    assert "Stopping" in view.status_label.text()


def test_bulk_progress_reports_position_and_updates_each_reading():
    view = _build(elevated=True)
    with patch("crapcleaner.gui.workers.DriveBulkWorker"):
        view._analyze_all()

    view._on_bulk_started("T:", 2, 2)
    assert "T: (2 of 2)" in view.status_label.text()

    view._on_bulk_progress("T:", True, "T: is 17% fragmented.", 17)
    assert view._frag_labels["T:"].text() == "17%"

    view._on_bulk_done(1, 2)
    assert "1 of 2" in view.status_label.text()


def test_a_partly_failed_sweep_is_reported_honestly():
    view = _build(elevated=True)
    with patch("crapcleaner.gui.workers.DriveBulkWorker"):
        view._analyze_all()
    view._on_bulk_done(0, 2)

    assert "0 of 2" in view.status_label.text()


def test_the_admin_caveat_is_said_once_not_once_per_drive():
    """Repeating the same machine-wide caveat under every row is noise, not information."""
    view = _build(elevated=False)

    assert _text_of(view).count(_NEEDS_ADMIN) == 1


def test_a_healthy_drive_gets_no_badge():
    """Five identical HEALTHY pills carry no signal; a badge should mean something is wrong."""
    view = _build(elevated=True)

    assert "HEALTHY" not in _text_of(view)


def test_a_shared_disk_is_named_once_above_its_volumes():
    view = _build(
        elevated=True,
        drives=[
            PhysicalDiskInfo(
                disk_number=0,
                model="ST2000DM006",
                media_type="HDD",
                health_status="Healthy",
                temperature_c=30,
                volumes=[
                    VolumeInfo(letter="D:", filesystem="NTFS", capacity=10, free_space=5),
                    VolumeInfo(letter="E:", filesystem="NTFS", capacity=10, free_space=5),
                ],
            )
        ],
    )

    assert _row_count(view) == 2
    # A heading, rather than the same model repeated under each of its volumes.
    assert _text_of(view).count("ST2000DM006") == 1


@contextmanager
def _running_on_linux(tools: bool, root: bool = False):
    """`tools` is whether fstrim/e4defrag are installed, which is what gates the actions."""
    with patch.object(drives_view_mod, "is_windows", return_value=False):
        with patch.object(drives_view_mod, "is_admin", return_value=root):
            with patch.object(drives_view_mod, "optimisation_supported", return_value=tools):
                with patch.object(drives_view_mod, "can_elevate", return_value=True):
                    yield


def _linux_view(drives=None, tools: bool = False, root: bool = False, schedule=None):
    with _running_on_linux(tools, root):
        view = DrivesView(main_window=None)
        view._drives = _sample_drives() if drives is None else drives
        view._schedule = schedule or ("Enabled", "systemd has not run a scheduled TRIM yet.")
        view._schedule_pending = False
        view._populate()
        return view


def test_without_the_linux_tools_the_optimisation_controls_are_absent_not_disabled():
    """A box with no fstrim cannot optimise anything; dead buttons for it are clutter."""
    view = _linux_view(tools=False)
    built = [b.text() for b in view.findChildren(QPushButton)]

    assert "Analyse" not in built
    assert "Optimise" not in built
    assert view.analyze_all_btn.isHidden()
    assert view.optimize_all_btn.isHidden()


def test_without_the_linux_tools_there_is_no_fragmentation_column_or_schedule_line():
    view = _linux_view(tools=False)
    text = _text_of(view)

    assert "FRAG" not in text
    assert "Windows" not in text
    assert not view.status_label.isVisibleTo(view)


def test_off_windows_the_drives_themselves_are_still_listed():
    """Health, capacity, and TRIM all read on Linux, so the table still earns its place."""
    view = _linux_view(tools=False)
    text = _text_of(view)

    assert "WD_BLACK SN770 1TB" in text
    assert "C:" in text
    assert "TRIM" in text
    assert "GB free" in text


def test_with_fstrim_installed_linux_gets_the_same_controls_windows_has():
    """fstrim and e4defrag answer the same two questions Optimize-Volume does."""
    view = _linux_view(tools=True, root=True)
    built = [b.text() for b in view.findChildren(QPushButton)]

    assert "Analyse" in built
    assert "Optimise" in built
    assert not view.analyze_all_btn.isHidden()
    assert view.analyze_all_btn.isEnabled()
    assert view.optimize_all_btn.isEnabled()
    assert "FRAG" in _text_of(view)


def test_root_counts_as_elevated_on_linux():
    """Gating the actions on is_windows() left a root session unable to run them."""
    assert _linux_view(tools=True, root=False).analyze_all_btn.isEnabled() is False
    assert _linux_view(tools=True, root=True).analyze_all_btn.isEnabled() is True


def test_the_relaunch_button_asks_for_root_not_admin_on_linux():
    view = _linux_view(tools=True)

    assert "Relaunch as Root" in _text_of(view)
    assert "Relaunch as Admin" not in _text_of(view)


def test_a_linux_reading_is_a_score_not_a_percentage():
    """e4defrag scores 0-100+; printing it as a percentage would state something false."""
    view = _linux_view(tools=True, root=True)
    with _running_on_linux(tools=True, root=True):
        view._on_analyzed("C:", True, "/: fragmentation score 12. No defrag needed.", 12)

    assert view._frag_labels["C:"].text() == "score 12"


def test_the_schedule_line_names_no_platform():
    """The same line covers ScheduledDefrag and fstrim.timer, so it names neither."""
    view = _linux_view(tools=True, root=True)

    assert "Scheduled optimisation: Enabled." in view.status_label.text()
    assert "Windows" not in view.status_label.text()


# --- opening the page ---------------------------------------------------------


def test_the_table_is_painted_from_the_cache_before_the_worker_starts():
    """The sidebar badge already claims a count; the page must not open empty."""
    with _running_as(True):
        view = DrivesView(main_window=None)

        with patch.object(
            drives_view_mod_drives, "cached_drives_report", return_value=_sample_drives()
        ):
            with patch("crapcleaner.gui.workers.DrivesWorker"):
                view.refresh_drives()

    assert _row_count(view) == 2
    assert "WD_BLACK SN770 1TB" in _text_of(view)


def test_the_banner_says_the_schedule_is_still_being_read():
    """Painting early must not report "Unknown" for an answer that has not arrived."""
    with _running_as(True):
        view = DrivesView(main_window=None)

        with patch.object(
            drives_view_mod_drives, "cached_drives_report", return_value=_sample_drives()
        ):
            with patch("crapcleaner.gui.workers.DrivesWorker"):
                view.refresh_drives()

        assert "Checking scheduled optimisation" in view.status_label.text()

        view._on_loaded(_sample_drives(), "Ready", "Last run yesterday.")

    assert "Scheduled optimisation: Ready." in view.status_label.text()
    assert "Checking" not in view.status_label.text()


def test_an_explicit_refresh_does_not_repaint_from_the_cache():
    """Refresh Drives means re-read the hardware, not redraw what is already shown."""
    with _running_as(True):
        view = DrivesView(main_window=None)

        with patch.object(drives_view_mod_drives, "cached_drives_report") as cached:
            with patch("crapcleaner.gui.workers.DrivesWorker"):
                view.refresh_drives(force=True)

    cached.assert_not_called()


def test_an_empty_cache_leaves_the_page_to_the_worker():
    with _running_as(True):
        view = DrivesView(main_window=None)

        with patch.object(drives_view_mod_drives, "cached_drives_report", return_value=None):
            with patch("crapcleaner.gui.workers.DrivesWorker") as worker:
                view.refresh_drives()

    assert _row_count(view) == 0
    worker.assert_called_once()
