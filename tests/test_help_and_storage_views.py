"""Tests for HelpSafetyView and StorageBreakdownView instantiation and diagnostics."""

from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication

from crapcleaner.gui.dialogs import HelpSafetyDialog
from crapcleaner.gui.views import HelpSafetyView, StorageBreakdownView

_app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])


def test_help_safety_view():
    mock_main = MagicMock()
    view = HelpSafetyView(mock_main)
    assert len(view._cards) >= 9
    assert view.search_edit is not None

    view._set_filter("REGISTRY")
    assert view._filter == "REGISTRY"
    reg_cards = [c for _, c, _ in view._cards if not c.isHidden()]
    assert len(reg_cards) >= 1

    view._set_filter("ALL")
    view.search_edit.setText("telemetry")
    visible_cards = [c for _, c, _ in view._cards if not c.isHidden()]
    assert len(visible_cards) >= 1


def test_help_safety_dialog():
    mock_main = MagicMock()
    dlg = HelpSafetyDialog(mock_main)
    assert dlg.help_view is not None
    assert len(dlg.help_view._cards) >= 9
    dlg.apply_theme("cyberpunk")
    assert dlg.help_view._theme == "cyberpunk"
    dlg.close()
    dlg.deleteLater()


def test_storage_breakdown_view():
    mock_main = MagicMock()
    view = StorageBreakdownView(mock_main)
    assert view.storage_grid is not None
    assert view.types_table is not None
    assert view.vm_table is not None
    assert view.favorite_combo is not None

    view._set_active_section("TYPES")
    assert view.content_stack.currentIndex() == 1

    view._set_active_section("OLD")
    assert view.content_stack.currentIndex() == 2

    view._set_active_section("VMS")
    assert view.content_stack.currentIndex() == 3


def test_storage_breakdown_presets_update_path():
    mock_main = MagicMock()
    view = StorageBreakdownView(mock_main)
    view._apply_storage_preset(view.path_edit.text())
    assert view.path_edit.text()


def test_is_worker_running_and_stop_worker_with_deleted_qobject():
    import shiboken6

    from crapcleaner.gui.workers import HealthWorker, is_worker_running, stop_worker

    assert is_worker_running(None) is False
    stop_worker(None)

    worker = HealthWorker()
    shiboken6.delete(worker)

    # Must return False, not raise libshiboken's "Internal C++ object already deleted".
    assert is_worker_running(worker) is False
    stop_worker(worker)
