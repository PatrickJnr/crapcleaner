"""The history view shows what a run removed, and offers to put it back."""

import json
import os
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from crapcleaner import history
from crapcleaner.config import config_dir
from crapcleaner.core.manifest import manifest_dir, write_manifest
from crapcleaner.gui.dialogs import RestoreRunDialog
from crapcleaner.gui.views.history import HistoryView
from crapcleaner.models.history import HistoryEntry
from crapcleaner.models.report import CleanupReport, RemovedPath


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


def _run(tmp_path, recycled=True, count=3):
    report = CleanupReport(started=datetime.now(), dry_run=False, use_recycle_bin=recycled)
    for index in range(count):
        report.removed.append(RemovedPath(str(tmp_path / f"file{index}.log"), 1024, recycled, 1))
    manifest_path = write_manifest(report, config_dir())
    assert manifest_path
    entry = HistoryEntry(
        kind="cleanup",
        started=report.started,
        files_removed=count,
        space_recovered=1024 * count,
        categories=["Temp Files"],
        use_recycle_bin=recycled,
        category_sizes={"temp": 1024 * count},
        manifest_path=manifest_path,
    )
    history.append(entry)
    return manifest_path


def test_the_view_reports_what_the_run_removed(app, tmp_path):
    _run(tmp_path)
    view = HistoryView(_Main())
    view.refresh()
    view.table.selectRow(0)
    assert "removed 3 item(s)" in view.detail_label.text()
    assert "3 went to the Recycle Bin" in view.detail_label.text()
    view.deleteLater()


def test_a_run_with_no_manifest_says_so_instead_of_showing_nothing(app):
    history.append(HistoryEntry(kind="cleanup", started=datetime.now(), dry_run=True))
    view = HistoryView(_Main())
    view.refresh()
    view.table.selectRow(0)
    assert "No per-file record" in view.detail_label.text()
    assert not view.restore_button.isEnabled()
    view.deleteLater()


def test_restore_is_offered_only_for_a_recycle_bin_run(app, tmp_path):
    _run(tmp_path, recycled=False)
    view = HistoryView(_Main())
    view.refresh()
    view.table.selectRow(0)
    assert not view.restore_button.isEnabled()
    view.deleteLater()

    history.clear()
    _run(tmp_path, recycled=True)
    view = HistoryView(_Main())
    view.refresh()
    view.table.selectRow(0)
    assert view.restore_button.isEnabled()
    view.deleteLater()


class _CapturedReport:
    shown: list = []

    def __init__(self, title, text, parent=None):
        _CapturedReport.shown.append(text)

    def exec(self):
        return 0


def test_the_detail_report_lists_every_path(app, tmp_path, monkeypatch):
    _run(tmp_path)
    view = HistoryView(_Main())
    view.refresh()
    _CapturedReport.shown.clear()
    monkeypatch.setattr("crapcleaner.gui.views.history.ReportDialog", _CapturedReport)
    view._show_details(view.table.item(0, 0))
    body = _CapturedReport.shown[-1]
    for index in range(3):
        assert str(tmp_path / f"file{index}.log") in body
    assert "[recycle bin]" in body
    assert "temp: " in body
    view.deleteLater()


def test_restore_dialog_lists_the_paths_rather_than_pretending(app, tmp_path):
    from PySide6.QtWidgets import QPlainTextEdit

    paths = [str(tmp_path / "a.log"), str(tmp_path / "b.log")]
    dialog = RestoreRunDialog(paths)
    listing = dialog.findChild(QPlainTextEdit)
    assert listing is not None
    for path in paths:
        assert path in listing.toPlainText()
    dialog.deleteLater()


def test_export_leaves_the_manifest_pointer_out(app, tmp_path, monkeypatch):
    _run(tmp_path)
    view = HistoryView(_Main())
    view.refresh()
    destination = tmp_path / "history.json"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(destination), "JSON (*.json)"),
    )
    view._export_json()
    records = json.loads(destination.read_text(encoding="utf-8"))
    assert records
    assert all("manifest_path" not in record for record in records)
    # The manifest itself stays in the config directory, unexported.
    assert os.listdir(manifest_dir(config_dir()))
    view.deleteLater()
