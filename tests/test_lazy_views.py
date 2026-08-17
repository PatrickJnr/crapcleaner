"""Pages are built on first use, without changing what callers see.

Building all sixteen views up front cost roughly two seconds of Qt widget assembly
before the window could appear. These tests pin the behaviour that makes deferring
them safe: stack order, theming, and attribute access all stay exactly as they were.
"""

from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

from crapcleaner.gui.app import MainWindow
from crapcleaner.gui.theme import THEMES

_app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])


@pytest.fixture
def window():
    win = MainWindow()
    yield win
    win.close()
    win.deleteLater()


def test_only_the_landing_page_is_built_at_startup(window):
    assert set(window._views) == {"dashboard"}
    # Every page still has a slot, so indices and shortcuts stay valid.
    assert window.stack.count() == len(window._PAGE_KEYS)


def test_attribute_access_builds_the_page(window):
    assert "cleanup" not in window._views
    view = window.cleanup_view
    assert view is not None
    assert "cleanup" in window._views
    # Second access returns the same object without rebuilding.
    assert window.cleanup_view is view


def test_navigation_builds_the_page(window):
    assert "settings" not in window._views
    window.navigate("settings")
    assert "settings" in window._views
    assert window.stack.currentIndex() == window._PAGE_KEYS.index("settings")


def test_pages_keep_their_declared_stack_order(window):
    """A page built late must still land in its original slot."""
    window.navigate("about")
    window.navigate("cleanup")
    for key in ("dashboard", "cleanup", "about"):
        view = window._views[key]
        assert window.stack.indexOf(view) == window._PAGE_KEYS.index(key)


def test_every_page_can_be_built_and_indexed(window):
    for key in window._PAGE_KEYS:
        window.navigate(key)
    assert set(window._views) == set(window._PAGE_KEYS)
    for key, view in window._views.items():
        assert window.stack.indexOf(view) == window._PAGE_KEYS.index(key)
    assert window.stack.count() == len(window._PAGE_KEYS)


def test_a_page_built_after_a_theme_change_uses_the_new_theme(window):
    window._apply_theme_to_views("light")
    assert "settings" not in window._views
    assert window.settings_view._theme == "light"


def test_theme_change_reaches_every_built_page(window):
    window.navigate("cleanup")
    window._apply_theme_to_views("dracula")
    assert window.dashboard._theme == "dracula"
    assert window.cleanup_view._theme == "dracula"


def test_theme_change_does_not_force_pages_into_existence(window):
    built = set(window._views)
    window._apply_theme_to_views("nord")
    assert set(window._views) == built


def test_all_themes_apply_across_all_pages(window):
    for key in window._PAGE_KEYS:
        window.navigate(key)
    for theme in THEMES:
        window._apply_theme_to_views(theme)


def test_unavailable_capability_pages_resolve_to_none():
    """A platform without a capability has no page and no widget for it."""
    with patch("crapcleaner.system.capabilities.is_windows", return_value=False):
        with patch("crapcleaner.system.capabilities.is_linux", return_value=True):
            with patch("crapcleaner.system.capabilities._has", return_value=False):
                win = MainWindow()

    try:
        assert "services" not in win._PAGE_KEYS
        assert win.services_view is None
        assert "services" not in win._views
        # Navigating to a page this platform lacks is a no-op, not a crash.
        win.navigate("services")
    finally:
        win.close()
        win.deleteLater()


def test_unknown_attribute_still_raises(window):
    with pytest.raises(AttributeError):
        window.definitely_not_a_view
