"""Unit tests for installer detection and crash dump analyzer."""

from unittest.mock import patch

from crapcleaner.analysis.crash_dumps import _extract_app_name, find_crash_dumps
from crapcleaner.analysis.installers import scan_installers


def test_extract_app_name():
    assert _extract_app_name("Discord.exe.12345.dmp") == "Discord.exe"
    assert _extract_app_name("chrome.exe.dmp") == "chrome.exe"
    assert _extract_app_name("system_error.dmp") == "system_error"


def test_find_crash_dumps(tmp_path):
    dmp_file = tmp_path / "app.exe.100.dmp"
    dmp_file.write_bytes(b"\x00" * 512)

    with patch("crapcleaner.analysis.crash_dumps.is_windows", return_value=True):
        with patch(
            "crapcleaner.analysis.crash_dumps.get_local_appdata", return_value=str(tmp_path)
        ):
            with patch(
                "crapcleaner.analysis.crash_dumps.get_windows_dir", return_value=str(tmp_path)
            ):
                crash_dir = tmp_path / "CrashDumps"
                crash_dir.mkdir()
                (crash_dir / "notepad.exe.500.dmp").write_bytes(b"\x00" * 1024)

                dumps = find_crash_dumps()
                assert any(d.application == "notepad.exe" for d in dumps)
                for d in dumps:
                    dt = d.to_dict()
                    assert "path" in dt
                    assert "dump_type" in dt


def test_scan_installers(tmp_path):
    (tmp_path / "vscode_setup_x64.exe").write_bytes(b"exe" * 500)
    (tmp_path / "package.msi").write_bytes(b"msi" * 500)
    (tmp_path / "image.iso").write_bytes(b"iso" * 500)
    (tmp_path / "document.pdf").write_bytes(b"pdf" * 500)

    installers = scan_installers(search_roots=[str(tmp_path)])
    names = [i.filename for i in installers]
    assert "vscode_setup_x64.exe" in names
    assert "package.msi" in names
    assert "image.iso" in names
    assert "document.pdf" not in names

    for item in installers:
        d = item.to_dict()
        assert "classification" in d
        assert d["classification"] == "Potentially removable installer"
