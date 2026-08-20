"""Auto-selected categories must not target installed applications or user data.

A SAFE or LOW_RISK category is ticked by default, so anything it claims is deleted by a
user who simply clicks Clean. Three categories claimed directories that are not caches:
winget's portable install root, Poetry's virtualenvs, and each snap's per-user data.
"""

import os
from unittest.mock import patch

from crapcleaner.categories import apps, python
from crapcleaner.registry import get_all_categories

# Directories that hold installed software or the user's own files rather than cache.
# Deliberately specific: plenty of real caches live under Program Files - Steam keeps
# appcache there - so a broad "installed software" heuristic only produces noise.
NEVER_AUTO_SELECTED = (
    os.path.join("microsoft", "winget", "packages"),
    os.path.join("pypoetry", "cache") + os.sep + "virtualenvs",
    os.path.join("pypoetry", "virtualenvs"),
)


def _is_per_snap_user_data(path: str) -> bool:
    """~/snap holds each snap's settings and saved files; /var/...snapd is its cache."""
    unix = path.replace("\\", "/")
    return "/snap/" in unix and not unix.startswith("/var/")


def _auto_selected(categories):
    # auto_selected is the per-category override and is None unless set; the resolved
    # answer, and what the interface ticks, is selected_by_default.
    return [c for c in categories if c.selected_by_default]


def test_no_auto_selected_category_targets_installed_software_or_user_data():
    offenders = []
    for category in _auto_selected(get_all_categories()):
        for target in category.targets:
            path = os.path.normcase(target.path).replace("/", os.sep)
            for forbidden in NEVER_AUTO_SELECTED:
                if forbidden in path:
                    offenders.append(f"{category.id} -> {target.path} ({forbidden})")
            if _is_per_snap_user_data(os.path.normcase(target.path)):
                offenders.append(f"{category.id} -> {target.path} (per-snap user data)")
    assert not offenders, "auto-selected categories claiming non-cache paths:\n" + "\n".join(
        offenders
    )


def test_winget_category_leaves_the_portable_install_root_alone():
    with (
        patch.object(apps, "is_windows", return_value=True),
        patch.object(apps, "is_linux", return_value=False),
    ):
        winget = next(c for c in apps.get_categories() if c.id == "winget_cache")
    paths = [os.path.normcase(t.path) for t in winget.targets]
    assert paths, "the category should still target the installer cache"
    assert not any(p.endswith(os.path.join("winget", "packages")) for p in paths)
    assert any("desktopappinstaller" in p for p in paths)


def test_poetry_category_leaves_project_virtualenvs_alone():
    poetry = next(c for c in python.get_categories() if c.id == "poetry_cache")
    paths = [os.path.normcase(t.path) for t in poetry.targets]
    assert paths
    assert not any(p.endswith(os.path.join("pypoetry", "cache")) for p in paths)
    assert all(p.endswith("cache") or p.endswith("artifacts") for p in paths)


def test_snap_category_leaves_per_snap_user_data_alone():
    with (
        patch.object(apps, "is_windows", return_value=False),
        patch.object(apps, "is_linux", return_value=True),
    ):
        snap = next(c for c in apps.get_categories() if c.id == "snap_cache")
    paths = [t.path.replace("\\", "/") for t in snap.targets]
    assert paths
    assert all(p.startswith("/var/") for p in paths), paths


def test_auto_selected_categories_explain_why_they_are_safe():
    selected = _auto_selected(get_all_categories())
    assert selected, "nothing is selected by default - the filter is wrong, not the data"
    silent = [c.id for c in selected if not (c.why_safe_to_delete or "").strip()]
    assert not silent, f"selected by default with no stated reason: {silent}"
