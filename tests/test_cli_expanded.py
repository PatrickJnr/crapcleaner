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


# --- drives -------------------------------------------------------------------


def _one_disk():
    from crapcleaner.system.drives import PhysicalDiskInfo, VolumeInfo

    return [
        PhysicalDiskInfo(
            disk_number=0,
            model="WD_BLACK SN770 1TB",
            media_type="NVMe SSD",
            bus_type="NVMe",
            health_status="Healthy",
            temperature_c=41,
            write_errors=None,
            volumes=[
                VolumeInfo(
                    letter="C:",
                    filesystem="NTFS",
                    capacity=1000,
                    free_space=400,
                    trim_supported=True,
                    trim_enabled=True,
                )
            ],
        )
    ]


def test_cli_drives_lists_disks_volumes_and_counters(capsys):
    with patch("crapcleaner.system.drives.get_drives_report", return_value=_one_disk()):
        with patch(
            "crapcleaner.system.drive_actions.scheduled_optimization_status",
            return_value=("Ready", "Never run."),
        ):
            assert run(["--drives"]) == 0

    out = capsys.readouterr().out
    assert "WD_BLACK SN770 1TB" in out
    assert "Temp: 41C" in out
    # A counter the controller did not report is absent, not zero.
    assert "Write errors" not in out
    assert "TRIM on" in out
    assert "Scheduled optimisation: Ready." in out


def test_cli_drives_as_json(capsys):
    with patch("crapcleaner.system.drives.get_drives_report", return_value=_one_disk()):
        assert run(["--drives", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["model"] == "WD_BLACK SN770 1TB"
    assert payload[0]["volumes"][0]["letter"] == "C:"


def test_cli_drives_hides_what_cannot_be_optimised(capsys):
    """A cloud mount has no media to inspect, so it is not a drive to report."""
    from crapcleaner.system.drives import UNMAPPED_DISK_NUMBER, PhysicalDiskInfo, VolumeInfo

    virtual = PhysicalDiskInfo(
        disk_number=UNMAPPED_DISK_NUMBER,
        model="Other volumes",
        media_type="Virtual / Removable",
        volumes=[VolumeInfo(letter="G:", filesystem="FAT32", capacity=10, free_space=5)],
    )
    with patch("crapcleaner.system.drives.get_drives_report", return_value=_one_disk() + [virtual]):
        with patch(
            "crapcleaner.system.drive_actions.scheduled_optimization_status",
            return_value=("Ready", ""),
        ):
            assert run(["--drives"]) == 0

    assert "G:" not in capsys.readouterr().out


def test_cli_analyse_reports_the_reading_and_fails_loudly(capsys):
    with patch(
        "crapcleaner.system.drive_actions.analyze_volume",
        return_value=(True, "C: is 17% fragmented.", 17),
    ):
        assert run(["--analyze-drive", "C"]) == 0
    assert "17% fragmented" in capsys.readouterr().out

    with patch(
        "crapcleaner.system.drive_actions.analyze_volume",
        return_value=(False, "C: could not be analysed. Access denied.", None),
    ):
        assert run(["--analyze-drive", "C"]) == 1
    assert "Access denied" in capsys.readouterr().out


def test_cli_optimise_is_a_dry_run_until_asked(capsys):
    """Optimising can run for hours, so it follows the same default the cleanup does."""
    with patch("crapcleaner.system.drive_actions.optimize_volume") as optimize:
        assert run(["--optimize-drive", "C"]) == 0

    optimize.assert_not_called()
    assert "Dry run" in capsys.readouterr().out


def test_cli_optimise_runs_when_asked(capsys):
    with patch(
        "crapcleaner.system.drive_actions.optimize_volume",
        return_value=(True, "C: optimised successfully."),
    ) as optimize:
        assert run(["--optimize-drive", "C", "--execute"]) == 0

    optimize.assert_called_once_with("C")
    assert "optimised successfully" in capsys.readouterr().out


def test_cli_drive_actions_do_not_open_the_gui():
    """A flag left out of the launch check starts the interface instead of running."""
    for argv in (["--drives"], ["--analyze-drive", "C"], ["--optimize-drive", "C"]):
        with patch("crapcleaner.gui.app.run_gui") as gui:
            with patch("crapcleaner.system.drives.get_drives_report", return_value=_one_disk()):
                with patch(
                    "crapcleaner.system.drive_actions.scheduled_optimization_status",
                    return_value=("Ready", ""),
                ):
                    with patch(
                        "crapcleaner.system.drive_actions.analyze_volume",
                        return_value=(True, "ok", 1),
                    ):
                        run(argv)

        gui.assert_not_called(), argv
