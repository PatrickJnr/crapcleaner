"""Tests for new gaming, developer, and application cleanup categories."""

from crapcleaner.categories.developer import get_categories as get_dev_categories
from crapcleaner.categories.gaming import get_categories as get_gaming_categories
from crapcleaner.registry import get_all_categories
from crapcleaner.utils.platform import is_linux, is_windows


def test_gaming_categories_expansion():
    """Gaming coverage is platform-specific: Linux gets Linux paths, not Windows ones."""
    cat_ids = {c.id for c in get_gaming_categories()}

    if is_linux():
        expected = {"steam_caches_linux", "heroic_cache_linux", "lutris_bottles_cache_linux"}
    elif is_windows():
        expected = {"fivem_cache", "directx_shader_cache", "launcher_caches", "steam_caches"}
    else:
        assert cat_ids == set(), "no gaming coverage is claimed for this platform"
        return

    assert cat_ids & expected, f"none of {sorted(expected)} in {sorted(cat_ids)}"


def test_developer_categories_expansion():
    cats = get_dev_categories()
    cat_ids = {c.id for c in cats}
    assert "vscode_caches" in cat_ids
    assert "github_desktop_cache" in cat_ids


def test_all_registered_categories():
    all_cats = get_all_categories()
    assert len(all_cats) >= 50
    # Every category must have an id, name, group, and safety level
    for c in all_cats:
        assert c.id
        assert c.name
        assert c.group
        assert c.safety_level
