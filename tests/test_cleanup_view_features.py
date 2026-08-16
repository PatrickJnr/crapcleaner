"""Focused tests for CleanupView explanation and scan-delta helpers."""

from unittest.mock import MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from crapcleaner.models.category import CleanupCategory, SafetyLevel
from crapcleaner.gui.views import CleanupView

_app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])


def _category() -> CleanupCategory:
    return CleanupCategory(
        id="browser_cache",
        name="Browser cache",
        description="Cached web assets.",
        safety_level=SafetyLevel.LOW_RISK,
        what_it_contains="Images, scripts, stylesheets.",
        why_it_grows="Browsers store assets locally.",
        why_safe_to_delete="They are re-downloaded automatically.",
        regeneration_behavior="Rebuilt during browsing.",
        reversible=True,
        size=1024 * 1024,
        item_count=5,
    )


def test_cleanup_view_explains_selected_category():
    view = CleanupView(MagicMock())
    category = _category()
    view.populate([category])
    item = view.tree.topLevelItem(0).child(0)
    view._on_current_item_changed(item, None)
    text = view.explain_label.text()
    assert "Browser cache" in text
    assert "Why it grows" in text
    assert "After cleanup" in text


def test_cleanup_view_scan_delta_message():
    view = CleanupView(MagicMock())
    category = _category()
    view.populate([category])
    previous = {"total_identified": 1024, "categories": {"browser_cache": 1024}}
    current = {"total_identified": 2048, "categories": {"browser_cache": 2048}}
    view.set_scan_delta(previous, current)
    assert "increased" in view.scan_delta_label.text()
    assert "Browser cache" in view.scan_delta_label.text()
