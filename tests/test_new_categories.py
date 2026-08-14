"""Tests for new gaming, developer, and application cleanup categories."""

from crapcleaner.developer.cleanup import get_categories as get_dev_categories
from crapcleaner.gaming.cleanup import get_categories as get_gaming_categories
from crapcleaner.registry import get_all_categories


def test_gaming_categories_expansion():
    cats = get_gaming_categories()
    cat_ids = {c.id for c in cats}
    # Check that new gaming categories exist
    assert (
        "fivem_cache" in cat_ids
        or "directx_shader_cache" in cat_ids
        or "launcher_caches" in cat_ids
        or "steam_caches" in cat_ids
    )


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
