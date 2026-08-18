"""The file-manager helper must stay on its own platform and quote safely."""

import os
from unittest.mock import patch

import pytest

from crapcleaner.utils import files as files_mod
from crapcleaner.utils.files import file_manager_name, reveal_in_file_manager


@pytest.fixture
def sample(tmp_path):
    target = tmp_path / "report.txt"
    target.write_text("x", encoding="utf-8")
    return str(target)


def _captured(calls):
    """Flatten Popen/run argument lists for inspection."""
    return [c[0][0] for c in calls if c[0]]


def test_windows_uses_explorer_with_list_arguments(sample):
    with patch.object(files_mod.os, "name", "nt"):
        with patch.object(files_mod.subprocess, "Popen") as popen:
            assert reveal_in_file_manager(sample) is True

    args = popen.call_args[0][0]
    assert isinstance(args, list), "arguments must never be a command string"
    assert args[0] == "explorer"
    assert args[1] == f"/select,{os.path.abspath(sample)}"


def test_a_quote_in_the_filename_cannot_alter_the_command(tmp_path):
    """Interpolating a path into a command string is how quoting bugs become bugs."""
    odd = tmp_path / "we'ird name.txt"
    odd.write_text("x", encoding="utf-8")

    with patch.object(files_mod.os, "name", "nt"):
        with patch.object(files_mod.subprocess, "Popen") as popen:
            reveal_in_file_manager(str(odd))

    args = popen.call_args[0][0]
    assert isinstance(args, list)
    # The whole path travels as one argument, quotes and spaces included.
    assert args[1].endswith("we'ird name.txt")
    assert len(args) == 2


def test_linux_never_invokes_explorer(sample):
    seen = []

    def fake_popen(args, *a, **k):
        seen.append(args)
        return None

    with patch.object(files_mod.os, "name", "posix"):
        with patch.object(
            files_mod, "which", side_effect=lambda t: f"/usr/bin/{t}" if t == "xdg-open" else None
        ):
            with patch.object(files_mod.subprocess, "Popen", side_effect=fake_popen):
                assert reveal_in_file_manager(sample) is True

    flat = [part for call in seen for part in call]
    assert "explorer" not in flat
    assert "xdg-open" in flat
    # xdg-open can only open the folder, so it receives the parent directory.
    assert os.path.dirname(os.path.abspath(sample)) in flat


def test_linux_prefers_the_freedesktop_interface_to_highlight_the_file(sample):
    with patch.object(files_mod.os, "name", "posix"):
        with patch.object(files_mod, "which", return_value="/usr/bin/dbus-send"):
            with patch.object(files_mod.subprocess, "run") as run:
                run.return_value.returncode = 0
                assert reveal_in_file_manager(sample) is True

    args = run.call_args[0][0]
    assert args[0] == "dbus-send"
    assert any(a.startswith("array:string:file://") for a in args)


def test_linux_falls_back_when_no_tooling_exists(sample):
    with patch.object(files_mod.os, "name", "posix"):
        with patch.object(files_mod, "which", return_value=None):
            assert reveal_in_file_manager(sample) is False


def test_missing_path_is_refused(tmp_path):
    assert reveal_in_file_manager(str(tmp_path / "nope.txt")) is False
    assert reveal_in_file_manager("") is False


def test_a_failing_launcher_never_raises(sample):
    with patch.object(files_mod.subprocess, "Popen", side_effect=OSError("boom")):
        assert reveal_in_file_manager(sample) is False


def test_menu_wording_follows_the_platform():
    with patch.object(files_mod.os, "name", "nt"):
        assert file_manager_name() == "File Explorer"
    with patch.object(files_mod.os, "name", "posix"):
        assert file_manager_name() == "File Manager"
