from crapcleaner.categories.developer import get_categories as get_dev_categories
from crapcleaner.categories.gaming import get_categories as get_gaming_categories
from crapcleaner.categories.node import get_categories as get_node_categories
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
    assert "claude_desktop_caches" in cat_ids
    assert "pub_cache" in cat_ids
    assert "zig_cache" in cat_ids
    assert "sccache" in cat_ids


def test_node_categories_expansion():
    cats = get_node_categories()
    cat_ids = {c.id for c in cats}
    assert "npm_cache" in cat_ids
    assert "yarn_cache" in cat_ids
    assert "pnpm_cache" in cat_ids
    assert "pnpm_store" in cat_ids
    assert "bun_cache" in cat_ids
    assert "deno_cache" in cat_ids


def test_browser_categories_expansion(tmp_path):
    from crapcleaner.categories.browsers import BROWSER_DISPLAY_NAMES, _firefox_categories

    assert "zen" in BROWSER_DISPLAY_NAMES
    assert BROWSER_DISPLAY_NAMES["zen"] == "Zen Browser"

    zen_profile = tmp_path / "zen" / "test.default"
    (zen_profile / "cache2").mkdir(parents=True)

    zen_cats = _firefox_categories("zen", "Zen Browser", str(tmp_path / "zen"))
    assert len(zen_cats) == 1
    assert zen_cats[0].id == "zen_cache"
    assert zen_cats[0].name == "Zen Browser cache"
    assert zen_cats[0].group == "Browsers"


def test_all_registered_categories():
    all_cats = get_all_categories()
    assert len(all_cats) >= 50
    for c in all_cats:
        assert c.id
        assert c.name
        assert c.group
        assert c.safety_level
        assert c.what_it_contains
        assert c.why_safe_to_delete


def test_script_extensions_stay_in_developer_files():
    from crapcleaner.analysis.file_types import FILE_CATEGORY_MAP

    for ext in (".sh", ".bat", ".ps1"):
        assert FILE_CATEGORY_MAP[ext] == "Developer files"
