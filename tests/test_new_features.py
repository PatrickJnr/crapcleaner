"""Tests for new developer categories, Windows SSL/Font caches, CLI options, and long-path utils."""

import json
import os

from crapcleaner.apps.cleanup import get_categories as get_apps_categories
from crapcleaner.cli import run
from crapcleaner.developer.cleanup import get_categories as get_dev_categories
from crapcleaner.registry import get_all_categories
from crapcleaner.utils.files import (
    normalize_long_path,
    path_is_locked,
    remove_file,
    remove_tree,
)
from crapcleaner.windows.cleanup import get_categories as get_win_categories


def test_developer_categories_expansion():
    categories = get_dev_categories()
    ids = {c.id for c in categories}
    assert "cargo_cache" in ids
    assert "go_cache" in ids
    assert "jvm_build_cache" in ids


def test_apps_categories_expansion():
    categories = get_apps_categories()
    ids = {c.id for c in categories}
    assert "discord_cache" in ids
    assert "slack_cache" in ids
    assert "spotify_cache" in ids
    assert "winget_cache" in ids
    assert "chocolatey_cache" in ids
    assert "scoop_cache" in ids


def test_windows_categories_expansion():
    categories = get_win_categories()
    ids = {c.id for c in categories}
    assert "windows_cryptnet_cache" in ids
    assert "windows_font_cache" in ids
    assert "windows_prefetch" in ids


def test_registry_has_expanded_categories():
    all_cats = get_all_categories()
    all_ids = {c.id for c in all_cats}
    assert "cargo_cache" in all_ids
    assert "go_cache" in all_ids
    assert "jvm_build_cache" in all_ids
    assert "windows_cryptnet_cache" in all_ids
    assert "windows_font_cache" in all_ids
    assert "windows_prefetch" in all_ids
    assert "discord_cache" in all_ids
    assert "winget_cache" in all_ids


def test_normalize_long_path():
    short = "C:\\Windows\\Temp\\file.txt"
    assert normalize_long_path(short) == os.path.abspath(short)

    fake_long = "C:\\" + "a" * 260 + "\\file.txt"
    normalized = normalize_long_path(fake_long)
    if os.name == "nt":
        assert normalized.startswith("\\\\?\\")


def test_remove_file_and_tree(tmp_path):
    f = tmp_path / "test_file.txt"
    f.write_text("hello world")
    assert f.exists()
    assert remove_file(str(f)) is True
    assert not f.exists()

    d = tmp_path / "sub_dir"
    d.mkdir()
    (d / "nested.txt").write_text("nested")
    assert d.exists()
    assert remove_tree(str(d)) is True
    assert not d.exists()


def test_path_is_locked_nonexistent():
    assert path_is_locked("C:\\nonexistent_file_path_12345.xyz") is False


def test_cli_list_categories(capsys):
    ret = run(["--list-categories"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Category ID" in captured.out
    assert "cargo_cache" in captured.out
    assert "windows_user_temp" in captured.out
    assert "winget_cache" in captured.out


def test_cli_list_categories_json(capsys):
    ret = run(["--list-categories", "--json"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list)
    ids = [item["id"] for item in data]
    assert "cargo_cache" in ids
    assert "discord_cache" in ids


def test_cli_duplicates_command(tmp_path, capsys):
    f1 = tmp_path / "dup1.bin"
    f2 = tmp_path / "dup2.bin"
    content = b"identical duplicate content for testing"
    f1.write_bytes(content)
    f2.write_bytes(content)

    ret = run(["--duplicates", str(tmp_path), "--min-dup-size", "10B"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "duplicate group" in captured.out


def test_cli_duplicates_json(tmp_path, capsys):
    f1 = tmp_path / "dup1.bin"
    f2 = tmp_path / "dup2.bin"
    content = b"identical duplicate content for json testing"
    f1.write_bytes(content)
    f2.write_bytes(content)

    ret = run(["--duplicates", str(tmp_path), "--min-dup-size", "10B", "--json"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["duplicate_count"] == 1


def test_cli_health_check(capsys):
    ret = run(["--health-check"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "CrapCleaner System Health & Storage Report" in captured.out


def test_cli_health_check_json(capsys):
    ret = run(["--health-check", "--json"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "drives" in data
    assert "total_capacity" in data


def test_cli_benchmark(capsys):
    ret = run(["--benchmark"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Benchmarking scanner traversal" in captured.out


def test_cli_benchmark_json(capsys):
    ret = run(["--benchmark", "--json"])
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "files_per_second" in data
