"""Tests for Python cache finders."""

import os

from crapcleaner.categories.python import (
    _is_skipped_dir,
    find_build_dirs,
    find_egg_info_dirs,
    find_pyc_files,
    find_pycache_dirs,
    get_categories,
)


def _make_tree(tmp_path, spec):
    for rel, content in spec.items():
        full = tmp_path / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content or "", encoding="utf-8")


class TestFinders:
    def test_find_pycache_dirs(self, tmp_path):
        _make_tree(
            tmp_path,
            {
                "module_a/__pycache__/a.cpython-311.pyc": "",
                "module_a/__pycache__/b.pyc": "",
                "src/app/__pycache__/c.pyc": "",
            },
        )
        found = find_pycache_dirs([str(tmp_path)])
        rels = {os.path.relpath(p, tmp_path) for p in found}
        assert rels == {
            os.path.join("module_a", "__pycache__"),
            os.path.join("src", "app", "__pycache__"),
        }

    def test_pycache_skips_venv_and_git(self, tmp_path):
        _make_tree(
            tmp_path,
            {
                ".venv/lib/__pycache__/x.pyc": "",
                ".git/objects/__pycache__/y.pyc": "",
                "real/__pycache__/z.pyc": "",
            },
        )
        found = find_pycache_dirs([str(tmp_path)])
        rels = {os.path.relpath(p, tmp_path) for p in found}
        assert rels == {os.path.join("real", "__pycache__")}

    def test_find_pyc_files_outside_pycache(self, tmp_path):
        _make_tree(
            tmp_path,
            {
                "loose.pyc": "",
                "module_a/__pycache__/ignored.pyc": "",
                "module_a/also.pyc": "",
            },
        )
        found = find_pyc_files([str(tmp_path)])
        rels = {os.path.relpath(p, tmp_path) for p in found}
        assert rels == {"loose.pyc", os.path.join("module_a", "also.pyc")}

    def test_find_egg_info(self, tmp_path):
        _make_tree(
            tmp_path,
            {
                "lib1/a.egg-info/PKG-INFO": "",
                "lib2/b.egg-info/PKG-INFO": "",
            },
        )
        found = find_egg_info_dirs([str(tmp_path)])
        assert len(found) == 2

    def test_find_build_dirs_requires_marker(self, tmp_path):
        _make_tree(
            tmp_path,
            {
                "lib_a/pyproject.toml": "",
                "lib_a/build/lib/__init__.py": "",
                "lib_b/build/lib/__init__.py": "",
            },
        )
        found = find_build_dirs([str(tmp_path)])
        rels = {os.path.relpath(p, tmp_path) for p in found}
        assert rels == {os.path.join("lib_a", "build")}

    def test_skipped_dirs(self):
        assert _is_skipped_dir(".git")
        assert _is_skipped_dir("node_modules")
        assert _is_skipped_dir(".hidden")
        assert not _is_skipped_dir("src")


class TestGetCategories:
    def test_returns_safe_defaults(self, tmp_path):
        cats = get_categories(scan_roots=[str(tmp_path)])
        ids = {c.id for c in cats}
        assert "pip_cache" in ids
        assert "uv_cache" in ids
        assert "pycache_dirs" in ids
        assert "pyc_files" in ids
        assert all(c.has_targets for c in cats)

    def test_default_scan_roots(self, tmp_path):
        # empty scan_roots should still produce defaults (no crash)
        cats = get_categories(scan_roots=[])
        assert len(cats) > 0

    def test_include_all_drives_adds_drive_roots(self, tmp_path, monkeypatch):
        monkeypatch.setattr("crapcleaner.categories.python.list_drives", lambda: ["C:\\", "D:\\"])
        cats = get_categories(scan_roots=[], include_all_drives=True)
        finder_cats = [c for c in cats if c.finder is not None]
        assert finder_cats, "expected at least one finder-based category"
        for cat in finder_cats:
            roots = cat.finder_args[0]
            assert "C:\\" in roots
            assert "D:\\" in roots

    def test_all_drives_off_keeps_configured_roots(self, tmp_path):
        cats = get_categories(scan_roots=[str(tmp_path)], include_all_drives=False)
        finder_cats = [c for c in cats if c.finder is not None]
        assert finder_cats
        for cat in finder_cats:
            roots = cat.finder_args[0]
            assert str(tmp_path) in roots
