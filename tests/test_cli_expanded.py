"""Unit tests for expanded CLI commands in CrapCleaner 1.0.3."""

import json
from datetime import datetime
from unittest.mock import patch

from crapcleaner.cli import run
from crapcleaner.core.manifest import MANIFEST_VERSION
from crapcleaner.history import append, clear
from crapcleaner.models.history import HistoryEntry


def test_cli_diagnostics_writes_a_bundle(tmp_path, capsys):
    destination = tmp_path / "bundle.txt"

    assert run(["diagnostics", "--output", str(destination)]) == 0
    assert "bundle.txt" in capsys.readouterr().out
    assert destination.read_text(encoding="utf-8").strip()


def test_cli_diagnostics_defaults_beside_the_log(capsys):
    from crapcleaner.config import config_dir

    assert run(["diagnostics"]) == 0
    assert config_dir() in capsys.readouterr().out


def test_cli_history_manifest_lists_what_a_run_removed(tmp_path, capsys):
    manifest = tmp_path / "run.json"
    manifest.write_text(
        json.dumps(
            {
                "version": MANIFEST_VERSION,
                "started": "2024-03-04T10:00:00",
                "items": [{"path": "/tmp/leftover.tmp", "size": 2048}],
            }
        ),
        encoding="utf-8",
    )
    clear()
    entry = HistoryEntry(kind="cleanup", started=datetime(2024, 3, 4, 10, 0))
    entry.manifest_path = str(manifest)
    append(entry)

    assert run(["history", "--manifest", "1"]) == 0
    assert "leftover.tmp" in capsys.readouterr().out


def test_cli_history_manifest_says_when_a_run_kept_none(capsys):
    clear()
    append(HistoryEntry(kind="cleanup", started=datetime(2024, 3, 4, 10, 0)))

    assert run(["history", "--manifest", "1"]) == 1
    assert "manifest" in capsys.readouterr().err.lower()


def test_cli_protected_paths():
    with patch("builtins.print") as mock_print:
        ret = run(["--protected-paths"])
        assert ret == 0
        mock_print.assert_called()


def test_cli_protected_paths_json(capsys):
    ret = run(["--protected-paths", "--json"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Protected Root" in captured.out


def test_cli_recycle_bin(capsys):
    ret = run(["--recycle-bin", "--json"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "total_size" in captured.out
    assert "item_count" in captured.out


def test_cli_disk_health(capsys):
    ret = run(["--disk-health", "--json"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "media_type" in captured.out


def test_cli_storage(tmp_path, capsys):
    test_file = tmp_path / "dummy.txt"
    test_file.write_text("storage test content")

    ret = run(["--storage", str(tmp_path), "--json"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "file_count" in captured.out


def test_cli_file_types(tmp_path, capsys):
    (tmp_path / "song.mp3").write_bytes(b"12345")
    ret = run(["--file-types", str(tmp_path), "--json"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Audio" in captured.out


def test_cli_installers(tmp_path, capsys):
    (tmp_path / "setup_app.exe").write_bytes(b"installer content")
    ret = run(["--installers", "--root", str(tmp_path), "--json"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "setup_app.exe" in captured.out


def test_cli_cleanup_preview(capsys, tmp_path):
    from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel

    dummy_cat = CleanupCategory(
        id="dummy_test_cat",
        name="Dummy Test Cat",
        description="Dummy desc",
        safety_level=SafetyLevel.SAFE,
        group="Test",
        targets=[CacheTarget(path=str(tmp_path))],
    )
    with patch("crapcleaner.cli.get_all_categories", return_value=[dummy_cat]):
        ret = run(["--cleanup-preview", "--json"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "total_estimated_size" in captured.out
        assert "categories" in captured.out


def test_cli_cache_report(capsys, tmp_path):
    from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel

    dummy_cat = CleanupCategory(
        id="dummy_cache_cat",
        name="Dummy Cache Cat",
        description="Dummy desc",
        safety_level=SafetyLevel.SAFE,
        group="Developer tools",
        targets=[CacheTarget(path=str(tmp_path))],
    )
    with patch("crapcleaner.cli.get_all_categories", return_value=[dummy_cat]):
        ret = run(["--cache-report", "--json"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "categories" in captured.out


def test_cli_history(capsys):
    ret = run(["--history", "--json"])
    assert ret == 0
    captured = capsys.readouterr()
    assert isinstance(captured.out, str)
