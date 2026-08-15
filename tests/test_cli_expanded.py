"""Unit tests for expanded CLI commands in CrapCleaner 1.0.3."""

from unittest.mock import patch

from crapcleaner.cli import run


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
