"""Regression tests for the 2026-08-19 audit: safety and security findings.

Each test reproduces the original failure mode rather than asserting that the new
implementation exists. Finding IDs refer to audit.md.
"""

import os
import sys
from unittest.mock import patch

import pytest

from crapcleaner.analysis.duplicates import find_duplicates
from crapcleaner.analysis.large_files import scan_large_files
from crapcleaner.core.cleaner import clean_categories, remove_selected_paths
from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel


def _write(path: str, data: str = "x") -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(data)
    return path


class TestPatternCleanupKeepsNonMatchingFiles:
    """SAFE-03: recursive cleanup with patterns removed whole sub-directories.

    The file loop honoured `patterns`, but the directory loop then deleted every
    sub-directory outright, taking the non-matching files inside it with them and
    skipping the per-file protected-path check on the way.
    """

    def _category(self, root: str) -> CleanupCategory:
        return CleanupCategory(
            id="pattern_target",
            name="Pattern target",
            group="Testing",
            description="",
            safety_level=SafetyLevel.SAFE,
            targets=[CacheTarget(path=root, patterns=("*.pf",), recurse=True)],
        )

    def test_nested_non_matching_files_survive(self, tmp_path):
        root = tmp_path / "prefetch"
        nested = root / "ReadyBoot" / "deeper"
        keep_top = _write(str(root / "notes.txt"), "keep me")
        keep_nested = _write(str(nested / "trace.etl"), "keep me too")
        remove_top = _write(str(root / "app.pf"))
        remove_nested = _write(str(nested / "other.pf"))

        report = clean_categories([self._category(str(root))], dry_run=False)

        assert os.path.exists(keep_top), "non-matching file in the target was deleted"
        assert os.path.exists(keep_nested), "non-matching file in a sub-directory was deleted"
        assert not os.path.exists(remove_top)
        assert not os.path.exists(remove_nested)
        assert report.total_files_deleted == 2

    def test_directory_holding_non_matching_files_is_kept(self, tmp_path):
        root = tmp_path / "cache"
        _write(str(root / "sub" / "keep.log"), "keep")
        _write(str(root / "sub" / "drop.pf"))

        clean_categories([self._category(str(root))], dry_run=False)

        assert (root / "sub").is_dir(), "directory removed even though a file remained"

    def test_emptied_nested_directory_is_removed(self, tmp_path):
        root = tmp_path / "cache"
        _write(str(root / "sub" / "deeper" / "only.pf"))

        clean_categories([self._category(str(root))], dry_run=False)

        assert not (root / "sub" / "deeper").exists(), "emptied directory left behind"

    def test_protected_directory_inside_a_target_is_not_removed(self, tmp_path):
        root = tmp_path / "cache"
        repo_file = _write(str(root / ".git" / "objects" / "abc"), "object")
        _write(str(root / "drop.pf"))

        report = clean_categories([self._category(str(root))], dry_run=False)

        assert os.path.exists(repo_file), "a .git directory inside a target was deleted"
        assert any("protected" in reason.lower() for reason in report.skip_reasons)

    def test_recovered_bytes_only_count_files_that_went(self, tmp_path):
        root = tmp_path / "cache"
        _write(str(root / "a.pf"), "0123456789")

        report = clean_categories([self._category(str(root))], dry_run=False)

        assert report.total_space_recovered == 10


class TestSelectedPathRemovalIsValidated:
    """SAFE-02: duplicate and large-file deletion bypassed the protected-path layer."""

    def test_protected_path_is_refused_with_a_reason(self, tmp_path):
        target = _write(str(tmp_path / "repo" / ".git" / "config"), "[core]")

        outcomes = remove_selected_paths([target], use_recycle_bin=False)

        assert len(outcomes) == 1
        assert outcomes[0].removed is False
        assert "protected" in outcomes[0].reason.lower()
        assert os.path.exists(target)

    def test_credential_file_is_refused(self, tmp_path):
        target = _write(str(tmp_path / ".ssh" / "id_rsa"), "KEY")

        outcomes = remove_selected_paths([target], use_recycle_bin=False)

        assert outcomes[0].removed is False
        assert os.path.exists(target)

    def test_ordinary_file_is_removed_and_reported(self, tmp_path):
        target = _write(str(tmp_path / "junk" / "cache.bin"))

        outcomes = remove_selected_paths([target], use_recycle_bin=False)

        assert outcomes[0].removed is True
        assert outcomes[0].reason == ""
        assert not os.path.exists(target)

    def test_missing_path_is_reported_not_claimed_as_removed(self, tmp_path):
        outcomes = remove_selected_paths([str(tmp_path / "gone.bin")], use_recycle_bin=False)

        assert outcomes[0].removed is False
        assert "no longer" in outcomes[0].reason.lower()

    def test_outcomes_are_per_path(self, tmp_path):
        good = _write(str(tmp_path / "junk" / "a.bin"))
        protected = _write(str(tmp_path / "proj" / ".git" / "HEAD"), "ref")

        outcomes = remove_selected_paths([good, protected], use_recycle_bin=False)

        assert [o.removed for o in outcomes] == [True, False]


class TestDiscoveryNeverOffersProtectedContent:
    """SAFE-02: protected content was presented as a deletion candidate."""

    def test_duplicate_finder_skips_git_objects(self, tmp_path):
        payload = "identical-content-" * 64
        _write(str(tmp_path / "work" / ".git" / "objects" / "aa" / "one"), payload)
        _write(str(tmp_path / "work" / ".git" / "objects" / "bb" / "two"), payload)

        groups = find_duplicates([str(tmp_path)], min_size_bytes=1)

        listed = [path for group in groups for path in group.files]
        assert not any(".git" in os.path.normpath(p).split(os.sep) for p in listed)

    def test_duplicate_finder_still_reports_ordinary_duplicates(self, tmp_path):
        payload = "identical-content-" * 64
        _write(str(tmp_path / "downloads" / "a.bin"), payload)
        _write(str(tmp_path / "downloads" / "b.bin"), payload)

        groups = find_duplicates([str(tmp_path)], min_size_bytes=1)

        assert len(groups) == 1
        assert len(groups[0].files) == 2

    def test_large_file_scan_skips_credentials(self, tmp_path):
        _write(str(tmp_path / ".ssh" / "id_rsa"), "K" * 4096)
        _write(str(tmp_path / "media" / "clip.mp4"), "V" * 4096)

        found = [item.path for item in scan_large_files(str(tmp_path), threshold_bytes=1)]

        assert any("clip.mp4" in p for p in found)
        assert not any("id_rsa" in p for p in found)


class TestDuplicateGroupAlwaysKeepsACopy:
    """SAFE-01: 'Select All' could recycle every copy in a group."""

    @pytest.fixture
    def dialog(self, qt_app, tmp_path):
        from crapcleaner.analysis.duplicates import DuplicateGroup
        from crapcleaner.gui.dialogs import DuplicateFilesDialog

        files = [str(tmp_path / name) for name in ("one.bin", "two.bin", "three.bin")]
        for path in files:
            _write(path, "same")
        return DuplicateFilesDialog(DuplicateGroup(size=4, files=files))

    def _check_all(self, dialog):
        from PySide6.QtCore import Qt

        for i in range(dialog.file_list.count()):
            dialog.file_list.item(i).setCheckState(Qt.CheckState.Checked)

    def test_selecting_every_copy_yields_no_targets(self, dialog):
        self._check_all(dialog)

        assert dialog.targets() == []

    def test_selecting_every_copy_disables_confirmation(self, dialog):
        self._check_all(dialog)

        assert dialog.recycle_button.isEnabled() is False
        assert dialog.keep_warning.isVisibleTo(dialog) is True

    def test_accept_refuses_while_no_copy_is_kept(self, dialog):
        from PySide6.QtWidgets import QDialog

        self._check_all(dialog)
        dialog.accept()

        assert dialog.result() != QDialog.DialogCode.Accepted

    def test_keeping_one_copy_allows_the_rest(self, dialog):
        from PySide6.QtCore import Qt

        self._check_all(dialog)
        dialog.file_list.item(0).setCheckState(Qt.CheckState.Unchecked)

        assert len(dialog.targets()) == 2
        assert dialog.recycle_button.isEnabled() is True


@pytest.mark.skipif(sys.platform != "win32", reason="Windows services backend")
class TestServiceNamesCannotInjectCommands:
    """SAFE-04: service names were interpolated into PowerShell -Command strings."""

    HOSTILE = "evil'; Remove-Item C:\\ -Recurse -Force #"

    def _capture(self, action, name):
        from crapcleaner.system.backends import services_windows as backend
        from crapcleaner.utils.platform import CommandResult

        seen = {}

        def fake_run(args, timeout=120.0, cwd=None, env_extra=None):
            seen.setdefault("calls", []).append((list(args), dict(env_extra or {})))
            return CommandResult(returncode=0)

        with (
            patch.object(backend, "run_command", fake_run),
            patch.object(backend, "is_admin", return_value=True),
        ):
            getattr(backend, action)(name)
        return seen["calls"]

    @pytest.mark.parametrize("action", ["start", "stop", "restart"])
    def test_hostile_name_never_reaches_the_command_text(self, action):
        calls = self._capture(action, self.HOSTILE)

        powershell = [(args, env) for args, env in calls if args and args[0] == "powershell"]
        assert powershell, "expected a PowerShell invocation"
        for args, env in powershell:
            assert not any(self.HOSTILE in part for part in args)
            assert not any("Remove-Item" in part for part in args)
            assert self.HOSTILE in env.values()

    @pytest.mark.parametrize(
        "name",
        ["plain", "with space", "quote'name", "semi;colon", "dollar$name", "back`tick"],
    )
    def test_awkward_names_are_passed_as_data(self, name):
        calls = self._capture("start", name)

        args, env = next((a, e) for a, e in calls if a and a[0] == "powershell")
        assert name not in " ".join(args)
        assert name in env.values()

    def test_startup_type_is_also_passed_as_data(self):
        from crapcleaner.system.backends import services_windows as backend
        from crapcleaner.utils.platform import CommandResult

        calls = []

        def fake_run(args, timeout=120.0, cwd=None, env_extra=None):
            calls.append((list(args), dict(env_extra or {})))
            return CommandResult(returncode=0)

        with (
            patch.object(backend, "run_command", fake_run),
            patch.object(backend, "is_admin", return_value=True),
        ):
            backend.set_startup_type(self.HOSTILE, "Manual")

        args, env = next((a, e) for a, e in calls if a and a[0] == "powershell")
        assert self.HOSTILE not in " ".join(args)
        assert self.HOSTILE in env.values()
        assert "Manual" in env.values()


class TestMemoryActionsReportHonestly:
    """SAFE-05, SAFE-06, SAFE-07."""

    def test_flush_all_fails_when_every_step_failed(self):
        from crapcleaner.system import memory_actions

        with (
            patch.object(memory_actions, "_trim_process_working_sets", return_value=(False, "no")),
            patch.object(memory_actions, "_trim_working_set", return_value=(False, "no")),
            patch.object(memory_actions, "is_admin", return_value=False),
        ):
            ok, message = memory_actions._flush_all()

        assert ok is False
        assert "Nothing was done" in message

    def test_flush_all_succeeds_when_one_step_worked(self):
        from crapcleaner.system import memory_actions

        with (
            patch.object(
                memory_actions, "_trim_process_working_sets", return_value=(True, "trimmed")
            ),
            patch.object(memory_actions, "_trim_working_set", return_value=(False, "no")),
            patch.object(memory_actions, "is_admin", return_value=False),
        ):
            ok, message = memory_actions._flush_all()

        assert ok is True
        assert "trimmed" in message

    def test_available_memory_delta_is_not_clamped_at_zero(self):
        from crapcleaner.system import memory_actions
        from crapcleaner.system.memory_report import MemoryStats

        stats = iter(
            [
                MemoryStats(total_bytes=100, available_bytes=60),
                MemoryStats(total_bytes=100, available_bytes=40),
            ]
        )
        with (
            patch.object(memory_actions, "get_memory_stats", lambda: next(stats)),
            patch.object(memory_actions, "_trim_working_set", return_value=(True, "done")),
        ):
            result = memory_actions.run_action("working_set")

        assert result.available_delta_bytes == -20

    def test_standby_effect_names_every_call_it_makes(self):
        from crapcleaner.system.memory_actions import get_action

        effect = get_action("standby_list").effect
        for call in (
            "MemoryFlushModifiedList",
            "MemoryEmptyWorkingSets",
            "MemoryPurgeStandbyList",
            "MemoryPurgeLowPriorityStandbyList",
            "SetSystemFileCacheSize",
        ):
            assert call in effect


class TestCorruptSettingsArePreserved:
    """SAFE-08: a damaged settings file was reset and then overwritten."""

    def test_damaged_file_is_moved_aside_and_reported(self, tmp_path, monkeypatch):
        from crapcleaner import config as config_module

        monkeypatch.setattr(config_module, "config_dir", lambda: str(tmp_path))
        path = os.path.join(str(tmp_path), "config.json")
        _write(path, '{"theme": "dracula", "excluded_paths": ["D:\\\\keep"]')  # truncated
        config_module.take_recovery_notice()

        settings = config_module.load_settings()

        assert settings["theme"] == "dark"
        assert os.path.exists(path + ".corrupt"), "the user's file was not preserved"
        with open(path + ".corrupt", encoding="utf-8") as fh:
            assert "D:\\\\keep" in fh.read()
        notice = config_module.take_recovery_notice()
        assert notice and "excluded paths" in notice

    def test_a_valid_file_is_left_alone(self, tmp_path, monkeypatch):
        from crapcleaner import config as config_module

        monkeypatch.setattr(config_module, "config_dir", lambda: str(tmp_path))
        path = os.path.join(str(tmp_path), "config.json")
        _write(path, '{"theme": "nord"}')

        assert config_module.load_settings()["theme"] == "nord"
        assert not os.path.exists(path + ".corrupt")
        assert config_module.take_recovery_notice() is None

    def test_non_object_json_is_also_quarantined(self, tmp_path, monkeypatch):
        from crapcleaner import config as config_module

        monkeypatch.setattr(config_module, "config_dir", lambda: str(tmp_path))
        path = os.path.join(str(tmp_path), "config.json")
        _write(path, "[1, 2, 3]")
        config_module.take_recovery_notice()

        config_module.load_settings()

        assert os.path.exists(path + ".corrupt")
