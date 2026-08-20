"""Recycling from the large files view runs off the GUI thread and takes a selection."""

import os
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QDialog

from crapcleaner.analysis.large_files import LargeFile
from crapcleaner.gui.dialogs import ConfirmDeleteDialog
from crapcleaner.gui.views.large_files import LargeFilesView


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture(autouse=True)
def silent_dialogs(monkeypatch):
    for name in ("information", "warning", "question", "critical"):
        monkeypatch.setattr(f"PySide6.QtWidgets.QMessageBox.{name}", lambda *a, **k: None)
    monkeypatch.setattr(
        ConfirmDeleteDialog, "exec", lambda self: QDialog.DialogCode.Accepted, raising=False
    )


class _Main:
    _settings: dict = {}


def _files(tmp_path, count=3):
    made = []
    for index in range(count):
        target = tmp_path / f"big{index}.bin"
        target.write_bytes(b"x" * 64)
        made.append(
            LargeFile(
                path=str(target),
                size=64,
                last_modified=datetime.now(),
                extension=".bin",
                file_type="bin",
            )
        )
    return made


def test_recycling_a_selection_leaves_the_gui_thread_free(app, tmp_path):
    from PySide6.QtCore import QThread

    view = LargeFilesView(_Main())
    files = _files(tmp_path)
    view.show_files(files)

    worker = view._recycle_paths([f.path for f in files[:2]])
    assert isinstance(worker, QThread)
    worker.wait(15000)
    app.processEvents()

    assert {f.path for f in view._files} == {files[2].path}
    assert not os.path.exists(files[0].path)
    assert os.path.exists(files[2].path)
    view.deleteLater()


def test_the_context_menu_acts_on_every_selected_row(app, tmp_path):
    view = LargeFilesView(_Main())
    files = _files(tmp_path, count=4)
    view.show_files(files)
    view.table.selectRow(0)
    view.table.selectRow(2)
    assert view._selected_paths() == [view.table.item(2, 4).text()]
    view.table.selectAll()
    assert len(view._selected_paths()) == 4
    view.deleteLater()


def test_an_empty_selection_recycles_nothing(app, tmp_path):
    view = LargeFilesView(_Main())
    view.show_files(_files(tmp_path))
    assert view._recycle_paths([]) is None
    assert len(view._files) == 3
    view.deleteLater()
