"""Tests for HelpSafetyView and StorageBreakdownView instantiation and diagnostics."""

from unittest.mock import MagicMock
from crapcleaner.gui.views import HelpSafetyView, StorageBreakdownView
from PySide6.QtWidgets import QApplication

# Ensure QApplication exists for GUI widget tests
_app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])


def test_help_safety_view():
    mock_main = MagicMock()
    view = HelpSafetyView(mock_main)
    assert len(view._cards) >= 9
    assert view.search_edit is not None

    # Test filter chips
    view._set_filter("REGISTRY")
    assert view._filter == "REGISTRY"
    reg_cards = [c for _, c, _ in view._cards if not c.isHidden()]
    assert len(reg_cards) >= 1

    # Reset filter and test search
    view._set_filter("ALL")
    view.search_edit.setText("telemetry")
    visible_cards = [c for _, c, _ in view._cards if not c.isHidden()]
    assert len(visible_cards) >= 1


def test_storage_breakdown_view():
    mock_main = MagicMock()
    view = StorageBreakdownView(mock_main)
    assert view.storage_grid is not None
    assert view.types_table is not None
    assert view.vm_table is not None

    # Test section switching
    view._set_active_section("TYPES")
    assert view.content_stack.currentIndex() == 1

    view._set_active_section("OLD")
    assert view.content_stack.currentIndex() == 2

    view._set_active_section("VMS")
    assert view.content_stack.currentIndex() == 3
