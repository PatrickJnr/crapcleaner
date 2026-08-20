"""Bulk keep rules, the group cap, and deletion moving off the GUI thread."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from crapcleaner.analysis.duplicates import DuplicateGroup
from crapcleaner.gui.dialogs import KEEP_RULES, BulkKeepRulesDialog, keep_index
from crapcleaner.gui.views.common import delete_paths
from crapcleaner.gui.views.duplicates import _MAX_DUPLICATE_GROUP_ROWS, DuplicatesView


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture(autouse=True)
def silent_message_boxes(monkeypatch):
    """QMessageBox blocks on its own event loop; offscreen there is nobody to click."""
    for name in ("information", "warning", "question", "critical"):
        monkeypatch.setattr(f"PySide6.QtWidgets.QMessageBox.{name}", lambda *a, **k: None)


def make_group(tmp_path, name, count=3, ages=None):
    folder = tmp_path / name
    folder.mkdir()
    paths = []
    for index in range(count):
        target = folder / f"copy{index}.bin"
        target.write_bytes(b"x" * 32)
        if ages:
            os.utime(target, (ages[index], ages[index]))
        paths.append(str(target))
    return DuplicateGroup(size=32, files=paths)


def test_keep_index_picks_by_rule(tmp_path):
    group = make_group(tmp_path, "g", 3, ages=[1_000_000, 3_000_000, 2_000_000])
    paths = group.files
    assert keep_index(paths, "first") == 0
    assert keep_index(paths, "oldest") == 0
    assert keep_index(paths, "newest") == 1
    assert keep_index(paths, "shortest") == 0
    assert keep_index([], "first") == -1


def test_folder_rule_keeps_the_copy_under_the_chosen_folder(tmp_path):
    keep_here = tmp_path / "keep"
    keep_here.mkdir()
    elsewhere = tmp_path / "other"
    elsewhere.mkdir()
    a, b = elsewhere / "f.bin", keep_here / "f.bin"
    a.write_bytes(b"x")
    b.write_bytes(b"x")
    paths = [str(a), str(b)]
    assert keep_index(paths, "folder", str(keep_here)) == 1
    # No folder chosen, or no copy inside it: fall back to the first copy.
    assert keep_index(paths, "folder", "") == 0
    assert keep_index(paths, "folder", str(tmp_path / "nowhere")) == 0


def test_folder_rule_is_offered(app, tmp_path):
    dialog = BulkKeepRulesDialog([make_group(tmp_path, "g")])
    offered = {dialog.rule_combo.itemData(i) for i in range(dialog.rule_combo.count())}
    assert offered == set(KEEP_RULES)
    dialog.deleteLater()


def test_bulk_rule_spares_one_copy_in_every_group(app, tmp_path):
    groups = [make_group(tmp_path, f"g{i}") for i in range(4)]
    dialog = BulkKeepRulesDialog(groups)
    targets = dialog.targets()
    assert len(targets) == sum(len(g.files) - 1 for g in groups)
    for group in groups:
        kept = [p for p in group.files if p not in targets]
        assert len(kept) == 1
    dialog.deleteLater()


def test_bulk_rule_previews_the_selection_before_anything_moves(app, tmp_path):
    groups = [make_group(tmp_path, f"g{i}") for i in range(3)]
    dialog = BulkKeepRulesDialog(groups)
    assert dialog.tree.topLevelItemCount() == 3
    outcomes = []
    for index in range(dialog.tree.topLevelItemCount()):
        parent = dialog.tree.topLevelItem(index)
        outcomes += [parent.child(i).text(1) for i in range(parent.childCount())]
    assert outcomes.count("Kept") == 3
    assert outcomes.count("Recycle") == 6
    assert "6 copy/copies would move" in dialog.summary.text()
    for path in (p for g in groups for p in g.files):
        assert os.path.exists(path)
    dialog.deleteLater()


def test_bulk_rule_covers_groups_the_table_never_rendered(app, tmp_path):
    groups = [make_group(tmp_path, f"g{i}", count=2) for i in range(5)]
    dialog = BulkKeepRulesDialog(groups)
    # Only a bounded number of groups are drawn, but every group is acted on.
    dialog.MAX_PREVIEW_GROUPS = 2
    dialog._refresh()
    assert dialog.tree.topLevelItemCount() == 2
    assert "3 more group(s)" in dialog.summary.text()
    assert len(dialog.targets()) == 5
    dialog.deleteLater()


class _Main:
    _settings: dict = {}

    def scan_duplicates(self, *_args):
        pass


def test_view_says_how_many_groups_are_not_shown(app, tmp_path):
    view = DuplicatesView(_Main())
    group = make_group(tmp_path, "g", count=2)
    view.show_groups([group] * (_MAX_DUPLICATE_GROUP_ROWS + 7))
    assert view.table.rowCount() == _MAX_DUPLICATE_GROUP_ROWS
    assert "7 group(s) are not listed here" in view.status_label.text()
    assert view.bulk_button.isEnabled()
    view.deleteLater()


def test_view_hides_the_note_when_every_group_fits(app, tmp_path):
    view = DuplicatesView(_Main())
    view.show_groups([make_group(tmp_path, "g", count=2)])
    assert "not listed here" not in view.status_label.text()
    view.deleteLater()


def test_a_group_left_with_one_copy_stops_being_a_group(app, tmp_path):
    view = DuplicatesView(_Main())
    group = make_group(tmp_path, "g", count=2)
    view.show_groups([group])

    class Outcome:
        def __init__(self, path):
            self.path, self.removed, self.reason = path, True, ""

    view._after_recycle([Outcome(group.files[1])])
    assert view._groups == []
    view.deleteLater()


def test_the_bulk_rule_reaches_groups_past_the_rendered_cap(app, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QDialog

    view = DuplicatesView(_Main())
    groups = [
        make_group(tmp_path, f"grp{i}", count=2) for i in range(_MAX_DUPLICATE_GROUP_ROWS + 3)
    ]
    view.show_groups(groups)
    beyond = groups[-1]

    monkeypatch.setattr(
        BulkKeepRulesDialog, "exec", lambda self: QDialog.DialogCode.Accepted, raising=False
    )
    worker = view._apply_bulk_rule()
    worker.wait(30000)
    app.processEvents()

    # The last group was never drawn, and its extra copy is gone anyway.
    assert not os.path.exists(beyond.files[1])
    assert os.path.exists(beyond.files[0])
    assert view._groups == []
    view.deleteLater()


def test_delete_paths_runs_off_the_gui_thread(app, tmp_path):
    """The whole point of GUI-03: the caller keeps its event loop."""
    from PySide6.QtCore import QThread

    target = tmp_path / "gone.bin"
    target.write_bytes(b"x" * 8)
    seen: list = []
    worker = delete_paths(None, [str(target)], seen.append)
    assert isinstance(worker, QThread)
    worker.wait(15000)
    app.processEvents()
    assert len(seen) == 1
    assert [o.path for o in seen[0]] == [str(target)]
    assert not target.exists()


def test_delete_paths_can_be_cancelled(app, tmp_path):
    targets = []
    for index in range(6):
        target = tmp_path / f"drop{index}.bin"
        target.write_bytes(b"x" * 8)
        targets.append(str(target))
    seen: list = []
    worker = delete_paths(None, targets, seen.append)
    worker.request_stop()
    worker.wait(15000)
    app.processEvents()
    # A stopped run still reports what it managed to remove rather than nothing.
    assert len(seen) == 1
    assert len(seen[0]) <= len(targets)
