"""Tests for the feature pack: sub-commands, preview, crash dumps, snapshots,
allocated size, scheduling, and self-update.

Nothing here touches the network or replaces a binary: the update tests drive the
real code with a local file server standing in for GitHub.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from unittest.mock import patch

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _write(path: str, data: str = "x") -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(data)
    return path


class TestSubCommands:
    """ARCH-02: sub-commands, without changing what the old flags do."""

    def test_a_command_translates_to_its_flag(self):
        from crapcleaner.commands import to_legacy_argv

        assert to_legacy_argv(["scan", "--json"]) == ["--scan", "--json"]
        assert to_legacy_argv(["capabilities"]) == ["--capabilities"]

    def test_a_positional_becomes_the_flag_value(self):
        from crapcleaner.commands import to_legacy_argv

        assert to_legacy_argv(["storage", "C:/tmp"]) == ["--storage", "C:/tmp"]
        assert to_legacy_argv(["large-files", "1GB"]) == ["--large-files", "1GB"]

    def test_clean_with_no_name_means_everything_safe(self):
        from crapcleaner.commands import to_legacy_argv

        assert to_legacy_argv(["clean"]) == ["--clean-safe"]

    def test_clean_with_names_targets_those_categories(self):
        from crapcleaner.commands import to_legacy_argv

        assert to_legacy_argv(["clean", "browser", "temp", "--execute"]) == [
            "--clean-category",
            "browser",
            "--clean-category",
            "temp",
            "--execute",
        ]

    def test_an_unknown_command_is_rejected(self):
        from crapcleaner.cli import run

        with pytest.raises(SystemExit) as excinfo:
            run(["not-a-command"])

        assert excinfo.value.code != 0

    def test_every_command_maps_to_a_real_flag(self):
        from crapcleaner.cli import build_parser
        from crapcleaner.commands import COMMANDS

        known = set()
        for action in build_parser()._actions:
            known.update(action.option_strings)

        for command in COMMANDS:
            assert command.flag in known, f"{command.name} maps to a flag that does not exist"

    def test_the_legacy_flags_still_work(self):
        from crapcleaner.cli import run

        assert run(["--capabilities"]) == 0

    def test_help_lists_commands(self, capsys):
        from crapcleaner.commands import build_command_parser

        with pytest.raises(SystemExit):
            build_command_parser().parse_args(["--help"])

        out = capsys.readouterr().out
        assert "scan" in out and "storage" in out


class TestCrashDumpExposure:
    """FEAT-05: the analyzer was implemented, tested, and unreachable."""

    def test_the_categories_are_registered(self):
        from crapcleaner.categories.crash_dumps import get_categories

        ids = {c.id for c in get_categories()}

        assert {"application_crash_dumps", "kernel_memory_dumps"} <= ids

    def test_kernel_dumps_need_elevation_and_review(self):
        from crapcleaner.categories.crash_dumps import get_categories

        kernel = next(c for c in get_categories() if c.id == "kernel_memory_dumps")

        assert kernel.requires_admin is True
        assert kernel.safety_level.value == "REVIEW"

    def test_the_finders_split_user_from_kernel_dumps(self, tmp_path):
        from crapcleaner.analysis import crash_dumps as module
        from crapcleaner.analysis.crash_dumps import CrashDumpItem

        items = [
            CrashDumpItem(
                path=str(tmp_path / "app.dmp"),
                filename="app.dmp",
                size=10,
                application="app.exe",
                created_at=None,
                modified_at=None,
                dump_type="User-mode crash dump",
            ),
            CrashDumpItem(
                path=str(tmp_path / "MEMORY.DMP"),
                filename="MEMORY.DMP",
                size=99,
                application="Windows Kernel",
                created_at=None,
                modified_at=None,
                dump_type="Full memory dump",
            ),
        ]
        with patch.object(module, "find_crash_dumps", return_value=items):
            assert module.find_application_dump_paths() == [str(tmp_path / "app.dmp")]
            assert module.find_kernel_dump_paths() == [str(tmp_path / "MEMORY.DMP")]

    def test_the_cli_lists_them(self, capsys):
        from crapcleaner.cli import run

        assert run(["crash-dumps"]) == 0
        assert "Crash Dumps" in capsys.readouterr().out


class TestCleanupExclusions:
    """FEAT-04: unticking a file in the preview must actually spare it."""

    def _category(self, root):
        from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel

        return CleanupCategory(
            id="probe",
            name="Probe",
            group="Testing",
            description="",
            safety_level=SafetyLevel.SAFE,
            targets=[CacheTarget(path=root)],
        )

    def test_an_excluded_file_is_left_on_disk(self, tmp_path):
        from crapcleaner.core.cleaner import clean_categories

        root = tmp_path / "cache"
        keep = _write(str(root / "keep.bin"), "keep")
        drop = _write(str(root / "drop.bin"), "drop")

        report = clean_categories([self._category(str(root))], dry_run=False, excluded_paths={keep})

        assert os.path.exists(keep), "a deselected file was deleted"
        assert not os.path.exists(drop)
        assert report.total_files_deleted == 1

    def test_an_excluded_file_deep_in_a_tree_is_left_alone(self, tmp_path):
        from crapcleaner.core.cleaner import clean_categories

        root = tmp_path / "cache"
        keep = _write(str(root / "deep" / "nested" / "keep.bin"), "keep")
        _write(str(root / "deep" / "nested" / "drop.bin"), "drop")

        clean_categories([self._category(str(root))], dry_run=False, excluded_paths={keep})

        assert os.path.exists(keep)

    def test_exclusions_are_matched_regardless_of_path_spelling(self, tmp_path):
        from crapcleaner.core.cleaner import clean_categories

        root = tmp_path / "cache"
        keep = _write(str(root / "keep.bin"), "keep")
        odd_spelling = os.path.join(str(root), ".", "keep.bin")

        clean_categories([self._category(str(root))], dry_run=False, excluded_paths={odd_spelling})

        assert os.path.exists(keep)

    def test_nothing_is_excluded_by_default(self, tmp_path):
        from crapcleaner.core.cleaner import clean_categories

        root = tmp_path / "cache"
        _write(str(root / "a.bin"))

        report = clean_categories([self._category(str(root))], dry_run=False)

        assert report.total_files_deleted == 1

    def test_the_dialog_reports_what_was_unticked(self, qt_app, tmp_path):
        from PySide6.QtCore import Qt

        from crapcleaner.gui.dialogs import CleanupPreviewDialog
        from crapcleaner.gui.workers import PreviewWorker

        root = tmp_path / "cache"
        first = _write(str(root / "one.bin"), "1")
        _write(str(root / "two.bin"), "2")

        with patch.object(PreviewWorker, "start", lambda self: None):
            dialog = CleanupPreviewDialog([self._category(str(root))])
            from crapcleaner.core.preview import generate_cleanup_preview

            dialog._show_preview(generate_cleanup_preview([self._category(str(root))]))

        top = dialog.tree.topLevelItem(0)
        for index in range(top.childCount()):
            child = top.child(index)
            if child.data(0, Qt.ItemDataRole.UserRole) == first:
                child.setCheckState(0, Qt.CheckState.Unchecked)

        assert dialog.excluded_paths() == {first}
        dialog.deleteLater()


class TestAllocatedSize:
    """FEAT-03: logical size is not what the drive reports as used."""

    def test_allocated_is_at_least_logical_for_small_files(self, tmp_path):
        from crapcleaner.analysis.storage import analyze_storage_hierarchy
        from crapcleaner.utils.disk_size import SIZE_ALLOCATED

        for index in range(10):
            _write(str(tmp_path / f"tiny{index}.bin"), "x")

        logical = analyze_storage_hierarchy(str(tmp_path))
        allocated = analyze_storage_hierarchy(str(tmp_path), size_mode=SIZE_ALLOCATED)

        assert allocated.size >= logical.size
        assert logical.file_count == allocated.file_count

    def test_a_tiny_file_occupies_at_least_a_block(self, tmp_path):
        from crapcleaner.utils.disk_size import allocated_size

        path = _write(str(tmp_path / "tiny.bin"), "x")

        assert allocated_size(path, os.stat(path)) >= 512

    def test_an_unreadable_file_falls_back_to_its_length(self, tmp_path):
        from crapcleaner.utils.disk_size import allocated_size

        path = _write(str(tmp_path / "gone.bin"), "abcdef")
        st = os.stat(path)
        os.remove(path)

        assert allocated_size(path, st) >= st.st_size

    def test_the_default_stays_logical(self, tmp_path):
        from crapcleaner.analysis.storage import analyze_storage_hierarchy

        payload = "0123456789" * 100
        _write(str(tmp_path / "one.bin"), payload)

        assert analyze_storage_hierarchy(str(tmp_path)).size == len(payload)


class TestStorageSnapshots:
    """FEAT-09: what grew since last time."""

    @pytest.fixture(autouse=True)
    def isolated(self, tmp_path, monkeypatch):
        from crapcleaner import config as config_module

        monkeypatch.setattr(config_module, "config_dir", lambda: str(tmp_path / "config"))

    def test_the_first_scan_has_nothing_to_compare_with(self, tmp_path):
        from crapcleaner.analysis.snapshots import compare, save_snapshot

        sizes = {str(tmp_path): 10 * 1024 * 1024}
        assert compare(str(tmp_path), sizes) is None
        assert save_snapshot(str(tmp_path), sizes) is not None

    def test_growth_is_reported_with_the_folder_that_grew(self, tmp_path):
        from crapcleaner.analysis.snapshots import compare, save_snapshot

        root = str(tmp_path)
        big = os.path.join(root, "games")
        save_snapshot(root, {root: 100 * 1024 * 1024, big: 50 * 1024 * 1024})

        comparison = compare(root, {root: 180 * 1024 * 1024, big: 130 * 1024 * 1024})

        assert comparison is not None
        assert comparison.total_delta == 80 * 1024 * 1024
        grew = {change.path: change.delta for change in comparison.growth()}
        assert grew[big] == 80 * 1024 * 1024
        assert all(change.kind == "grew" for change in comparison.growth())

    def test_a_removed_folder_is_reported_as_shrinkage(self, tmp_path):
        from crapcleaner.analysis.snapshots import compare, save_snapshot

        root = str(tmp_path)
        gone = os.path.join(root, "old-vm")
        save_snapshot(root, {root: 90 * 1024 * 1024, gone: 40 * 1024 * 1024})

        comparison = compare(root, {root: 50 * 1024 * 1024})

        assert any(c.path == gone and c.kind == "removed" for c in comparison.changes)

    def test_small_changes_are_not_reported(self, tmp_path):
        from crapcleaner.analysis.snapshots import compare, save_snapshot

        root = str(tmp_path)
        folder = os.path.join(root, "logs")
        save_snapshot(root, {root: 10 * 1024 * 1024, folder: 5 * 1024 * 1024})

        comparison = compare(root, {root: 10 * 1024 * 1024, folder: 5 * 1024 * 1024 + 1024})

        assert comparison.changes == []

    def test_the_stored_file_is_bounded(self, tmp_path):
        from crapcleaner.analysis import snapshots

        root = str(tmp_path)
        sizes = {f"{root}/dir{index}": 2 * 1024 * 1024 for index in range(50)}
        sizes[root] = 100 * 1024 * 1024

        with patch.object(snapshots, "MAX_TRACKED_DIRS", 10):
            path = snapshots.save_snapshot(root, sizes)

        with open(path, encoding="utf-8") as fh:
            assert len(json.load(fh)["dirs"]) == 10

    def test_tiny_directories_are_not_stored(self, tmp_path):
        from crapcleaner.analysis.snapshots import load_snapshot, save_snapshot

        root = str(tmp_path)
        save_snapshot(root, {root: 50 * 1024 * 1024, f"{root}/small": 1024})

        assert f"{root}/small" not in load_snapshot(root)["dirs"]


class TestScheduling:
    """FEAT-01: real scheduling, and a scheduled run that cannot delete."""

    @pytest.fixture(autouse=True)
    def isolated(self, tmp_path, monkeypatch):
        from crapcleaner import config as config_module

        monkeypatch.setattr(config_module, "config_dir", lambda: str(tmp_path / "config"))

    def test_the_time_of_day_is_validated(self):
        from crapcleaner.core.scheduler import _valid_time

        assert _valid_time("9:05") == "09:05"
        for bad in ("25:00", "abc", "12", "12:99", "12:00; shutdown"):
            with pytest.raises(ValueError):
                _valid_time(bad)

    def test_the_scheduled_command_names_the_scan(self):
        from crapcleaner.core.scheduler import launch_command

        assert launch_command()[-1] == "scheduled-scan"

    def test_a_scheduled_run_never_cleans(self, monkeypatch):
        from datetime import datetime

        import crapcleaner.core.scheduler as scheduler
        from crapcleaner.models.report import ScanReport

        def explode(*_args, **_kwargs):
            raise AssertionError("a scheduled run tried to delete something")

        monkeypatch.setattr("crapcleaner.core.cleaner.clean_categories", explode)
        report = ScanReport(started=datetime.now())
        with (
            patch("crapcleaner.registry.get_all_categories", return_value=[]),
            patch("crapcleaner.core.scanner.ScanEngine.run", return_value=report),
        ):
            result = scheduler.run_scheduled_scan()

        assert result["total_reclaimable"] == 0

    def test_the_result_is_recorded_for_the_interface(self, monkeypatch):
        from datetime import datetime

        import crapcleaner.core.scheduler as scheduler
        from crapcleaner.models.report import ScanCategoryResult, ScanReport

        report = ScanReport(started=datetime.now())
        report.results.append(
            ScanCategoryResult(
                category_id="temp",
                name="Temp",
                size=9 * 1024**3,
                item_count=12,
                skipped=0,
                safety_level="SAFE",
                group="Windows",
                description="",
                reclaimable=True,
            )
        )
        with (
            patch("crapcleaner.registry.get_all_categories", return_value=[]),
            patch("crapcleaner.core.scanner.ScanEngine.run", return_value=report),
            patch.object(scheduler, "notify", return_value=True) as notify,
        ):
            scheduler.run_scheduled_scan()

        stored = scheduler.last_result()
        assert stored["total_reclaimable"] == 9 * 1024**3
        assert stored["threshold_exceeded"] is True
        notify.assert_called_once()

    def test_below_the_threshold_nothing_interrupts_the_user(self, monkeypatch):
        from datetime import datetime

        import crapcleaner.core.scheduler as scheduler
        from crapcleaner.models.report import ScanReport

        with (
            patch("crapcleaner.registry.get_all_categories", return_value=[]),
            patch(
                "crapcleaner.core.scanner.ScanEngine.run",
                return_value=ScanReport(started=datetime.now()),
            ),
            patch.object(scheduler, "notify") as notify,
        ):
            scheduler.run_scheduled_scan()

        notify.assert_not_called()

    def test_status_reports_when_scheduling_is_unavailable(self):
        import crapcleaner.core.scheduler as scheduler

        with patch.object(scheduler, "is_supported", return_value=False):
            state = scheduler.status()

        assert state.supported is False
        assert state.registered is False
        assert "not available" in state.detail


class TestSelfUpdate:
    """The update flow: download, verify, and only then replace."""

    def _serve(self, tmp_path, payload: bytes, checksums: str):
        """A stand-in for the release assets, on disk."""
        release = tmp_path / "release"
        release.mkdir(parents=True, exist_ok=True)
        from crapcleaner.utils.self_update import asset_name

        (release / asset_name()).write_bytes(payload)
        (release / "checksums.txt").write_text(checksums, encoding="utf-8")
        return release.as_uri()

    @pytest.fixture
    def frozen(self, tmp_path, monkeypatch):
        """Pretend to be a one-file build living in tmp_path."""
        import crapcleaner.utils.self_update as module

        executable = tmp_path / ("CrapCleaner.exe" if os.name == "nt" else "crapcleaner")
        executable.write_bytes(b"MZ old" if os.name == "nt" else b"\x7fELF old")
        monkeypatch.setattr(sys, "executable", str(executable))
        monkeypatch.setattr(module, "can_self_update", lambda: (True, ""))
        return executable

    def _payload(self) -> bytes:
        head = b"MZ" if os.name == "nt" else b"\x7fELF"
        return head + b"\x00new release payload"

    def test_a_source_checkout_is_told_what_to_do_instead(self):
        from crapcleaner.utils.self_update import can_self_update, install_kind

        assert install_kind() == "source"
        allowed, reason = can_self_update()
        assert allowed is False
        assert "git pull" in reason

    def test_a_verified_download_is_kept(self, tmp_path, frozen):
        from crapcleaner.utils.self_update import asset_name, download_update

        payload = self._payload()
        digest = hashlib.sha256(payload).hexdigest()
        base = self._serve(tmp_path, payload, f"{digest}  {asset_name()}\n")

        update = download_update("1.2.3", base_url=base)

        assert update.sha256 == digest
        assert os.path.isfile(update.path)
        assert open(update.path, "rb").read() == payload
        # The running application is untouched until apply_update runs.
        assert frozen.read_bytes().startswith(b"MZ old" if os.name == "nt" else b"\x7fELF old")

    def test_a_wrong_checksum_is_refused_and_the_file_discarded(self, tmp_path, frozen):
        from crapcleaner.utils.self_update import UpdateError, asset_name, download_update

        base = self._serve(tmp_path, self._payload(), f"{'0' * 64}  {asset_name()}\n")

        with pytest.raises(UpdateError) as excinfo:
            download_update("1.2.3", base_url=base)

        assert "checksum" in str(excinfo.value)
        leftovers = [p for p in os.listdir(os.path.dirname(str(frozen))) if "update" in p]
        assert leftovers == []

    def test_a_missing_checksum_entry_stops_the_update(self, tmp_path, frozen):
        from crapcleaner.utils.self_update import UpdateError, download_update

        base = self._serve(tmp_path, self._payload(), "deadbeef  something-else.bin\n")

        with pytest.raises(UpdateError) as excinfo:
            download_update("1.2.3", base_url=base)

        assert "checksum" in str(excinfo.value)

    def test_a_payload_that_is_not_an_executable_is_refused(self, tmp_path, frozen):
        from crapcleaner.utils.self_update import UpdateError, asset_name, download_update

        payload = b"<html>404</html>"
        digest = hashlib.sha256(payload).hexdigest()
        base = self._serve(tmp_path, payload, f"{digest}  {asset_name()}\n")

        with pytest.raises(UpdateError) as excinfo:
            download_update("1.2.3", base_url=base)

        assert "not an executable" in str(excinfo.value)

    def test_the_digest_is_read_from_a_checksums_listing(self):
        from crapcleaner.utils.self_update import expected_digest

        listing = (
            f"{'a' * 64}  CrapCleaner.exe\n"
            f"{'b' * 64}  crapcleaner-linux-x86_64\n"
            "not-a-digest  junk.bin\n"
        )

        assert expected_digest(listing, "CrapCleaner.exe") == "a" * 64
        assert expected_digest(listing, "crapcleaner-linux-x86_64") == "b" * 64
        assert expected_digest(listing, "junk.bin") is None
        assert expected_digest(listing, "missing.bin") is None

    def test_the_installer_waits_for_this_process_and_can_roll_back(self, tmp_path, frozen):
        from crapcleaner.utils.self_update import DownloadedUpdate, write_installer_script

        update = DownloadedUpdate(
            version="1.2.3",
            path=str(tmp_path / "new.bin"),
            size=10,
            sha256="0" * 64,
            target=str(frozen),
        )

        script = write_installer_script(update)
        body = open(script, encoding="utf-8").read()

        assert str(os.getpid()) in body, "the installer does not wait for this process"
        assert ".bak" in body, "no backup is kept"
        assert str(frozen) in body
        os.remove(script)

    def test_applying_without_a_downloaded_file_is_refused(self, tmp_path, frozen):
        from crapcleaner.utils.self_update import DownloadedUpdate, UpdateError, apply_update

        update = DownloadedUpdate(
            version="1.2.3",
            path=str(tmp_path / "not-there.bin"),
            size=0,
            sha256="0" * 64,
            target=str(frozen),
        )

        with pytest.raises(UpdateError):
            apply_update(update)

    @pytest.mark.skipif(os.name == "nt", reason="uses /bin/sh to run the generated script")
    def test_the_installer_really_replaces_the_binary(self, tmp_path, frozen):
        """End to end, with a short-lived process standing in for the application."""
        from crapcleaner.utils.self_update import DownloadedUpdate, write_installer_script

        new_file = tmp_path / "new.bin"
        new_file.write_bytes(b"\x7fELF new")

        # A process that exits immediately, so the installer's wait loop completes.
        victim = subprocess.Popen(["/bin/sh", "-c", "exit 0"])
        victim.wait()

        update = DownloadedUpdate(
            version="1.2.3", path=str(new_file), size=8, sha256="0" * 64, target=str(frozen)
        )
        script = write_installer_script(update)
        body = open(script, encoding="utf-8").read().replace(str(os.getpid()), str(victim.pid))
        # Do not relaunch a fake binary during the test.
        body = body.replace('"$TARGET" ', ': "$TARGET" ')
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(body)

        subprocess.run(["/bin/sh", script], timeout=30, check=False)
        for _ in range(20):
            if frozen.read_bytes() == b"\x7fELF new":
                break
            time.sleep(0.1)

        assert frozen.read_bytes() == b"\x7fELF new"

    def test_the_cli_reports_when_it_is_already_current(self, capsys):
        from crapcleaner.cli import run
        from crapcleaner.utils.updater import UpdateInfo

        current = UpdateInfo(
            current_version="1.0.0",
            latest_version="1.0.0",
            is_newer=False,
            release_name="",
            html_url="",
            published_at="",
            body="",
        )
        with patch("crapcleaner.utils.updater.check_for_updates", return_value=current):
            assert run(["update"]) == 0

        assert "latest release" in capsys.readouterr().out

    def test_the_cli_does_not_install_without_confirmation(self, capsys):
        from crapcleaner.cli import run
        from crapcleaner.utils.updater import UpdateInfo

        newer = UpdateInfo(
            current_version="1.0.0",
            latest_version="9.9.9",
            is_newer=True,
            release_name="",
            html_url="https://example.invalid",
            published_at="",
            body="",
        )
        with (
            patch("crapcleaner.utils.updater.check_for_updates", return_value=newer),
            patch("crapcleaner.utils.self_update.can_self_update", return_value=(True, "")),
            patch("crapcleaner.cli._confirm_execute", return_value=False),
            patch("crapcleaner.utils.self_update.download_update") as download,
        ):
            assert run(["update", "install"]) == 1

        download.assert_not_called()
        assert "cancelled" in capsys.readouterr().out.lower()
