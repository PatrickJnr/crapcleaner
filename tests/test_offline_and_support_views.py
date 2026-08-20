"""Offline mode where the user sees it, the diagnostics bundle, and regrowth."""

import os
from datetime import datetime, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QLabel

from crapcleaner import history
from crapcleaner.config import save_settings
from crapcleaner.gui.views.about import AboutView
from crapcleaner.gui.views.cleanup import NOT_ENOUGH_HISTORY, regrowth_text
from crapcleaner.gui.views.help_safety import HelpSafetyView
from crapcleaner.gui.views.settings import SettingsView
from crapcleaner.gui.views.updates import AppUpdatesView
from crapcleaner.models.history import HistoryEntry


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture(autouse=True)
def silent_message_boxes(monkeypatch):
    for name in ("information", "warning", "question", "critical"):
        monkeypatch.setattr(f"PySide6.QtWidgets.QMessageBox.{name}", lambda *a, **k: None)


class _Main:
    _settings: dict = {}
    _theme = "dark"

    def apply_settings(self):
        pass


def test_about_does_not_fetch_contributors_offline(app, monkeypatch):
    save_settings({"offline_mode": True})
    started = []
    monkeypatch.setattr(
        "crapcleaner.gui.workers.ContributorsWorker",
        lambda **kwargs: started.append(kwargs) or (_ for _ in ()).throw(AssertionError),
    )
    view = AboutView(_Main())
    view._populate_contributors()
    assert not started
    labels = [w.text() for w in view.contrib_grid.parentWidget().findChildren(QLabel) if w.text()]
    assert any("Offline mode is on" in text for text in labels)
    view.deleteLater()


def test_about_update_check_says_it_was_skipped_not_that_it_failed(app, monkeypatch):
    save_settings({"offline_mode": True})
    shown = []
    monkeypatch.setattr(
        "PySide6.QtWidgets.QMessageBox.information",
        lambda parent, title, text, *a, **k: shown.append(text),
    )
    monkeypatch.setattr(
        "crapcleaner.gui.workers.UpdateCheckWorker",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("network worker started")),
    )
    view = AboutView(_Main())
    view._check_updates()
    assert shown and "Offline mode is on" in shown[0]
    assert "Could not connect" not in shown[0]
    view.deleteLater()


def test_updates_view_reports_the_skip_rather_than_an_error(app, monkeypatch):
    save_settings({"offline_mode": True})
    monkeypatch.setattr(
        "crapcleaner.gui.workers.PackageManagerWorker",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("network worker started")),
    )
    view = AppUpdatesView(_Main())
    view.refresh()
    assert view.hero_badge.text() == "OFFLINE MODE"
    assert "offline mode is on" in view.status_label.text()
    assert "Failed" not in view.status_label.text()
    view.deleteLater()


def test_settings_offers_the_offline_and_high_contrast_controls(app):
    save_settings({"offline_mode": True, "high_contrast": True})
    view = SettingsView(_Main())
    assert view.offline_check.isChecked()
    assert view.high_contrast_check.isChecked()
    view.deleteLater()


def test_diagnostics_clipboard_and_bundle_share_one_source(app, tmp_path, monkeypatch):
    view = HelpSafetyView(_Main())
    view._copy_diagnostics()
    copied = app.clipboard().text()
    assert copied.startswith("=== CrapCleaner Diagnostics ===")
    assert "--- Capabilities ---" in copied

    destination = tmp_path / "bundle.txt"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(destination), "Text (*.txt)"),
    )
    worker = view._save_diagnostics_bundle()
    worker.wait(15000)
    app.processEvents()
    written = destination.read_text(encoding="utf-8")
    # Both come from build_diagnostics_text, so only the timestamp line differs.
    assert written.splitlines()[0] == copied.splitlines()[0]
    assert written.splitlines()[2] == copied.splitlines()[2]
    assert view.bundle_button.isEnabled()
    view.deleteLater()


def test_regrowth_reads_as_not_enough_history_rather_than_zero():
    assert history.regrowth_estimate("temp") is None
    text = regrowth_text("temp")
    assert NOT_ENOUGH_HISTORY in text
    assert "0 B" not in text
    assert "never cleaned here" in text


def test_regrowth_is_a_rate_once_there_is_history():
    now = datetime.now()
    for weeks_ago in (4, 2, 0):
        history.append(
            HistoryEntry(
                kind="cleanup",
                started=now - timedelta(weeks=weeks_ago),
                category_sizes={"temp": 1024 * 1024 * 100},
                categories=["Temp Files"],
            )
        )
    text = regrowth_text("temp")
    assert "per week" in text
    assert "last cleaned" in text
    assert NOT_ENOUGH_HISTORY not in text
