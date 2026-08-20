"""Every interactive widget a view builds must announce itself.

Accessible names were a habit before this: 13 of 193 interactive widgets had one.
This walks the constructed views and dialogs and fails when a control offers a
screen reader nothing to read.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSlider,
    QTabBar,
    QToolButton,
    QWidget,
)

from crapcleaner.analysis.duplicates import DuplicateGroup
from crapcleaner.gui.app import MainWindow
from crapcleaner.gui.dialogs import (
    BulkKeepRulesDialog,
    ConfirmDeleteDialog,
    DuplicateFilesDialog,
    ReportDialog,
    RestoreRunDialog,
)

#: Controls a user can operate. Labels, frames and separators are not on this list
#: because there is nothing to operate.
INTERACTIVE = (
    QPushButton,
    QCheckBox,
    QRadioButton,
    QToolButton,
    QComboBox,
    QLineEdit,
    QAbstractSpinBox,
    QSlider,
    QAbstractItemView,
    QTabBar,
)

#: Controls whose own label is their accessible name; the rest need one set.
SELF_LABELLING = (QPushButton, QCheckBox, QRadioButton, QToolButton)

#: Exemptions, each with the reason it is not a control a user operates on its own.
#: A reviewer should be able to disagree with an entry here, which is why it is a
#: list and not a silent skip.
EXEMPT_REASONS = {
    "nested": (
        "A widget Qt builds inside another control - a spin box's editor, a combo "
        "box's popup list, a table's header and corner button. It is reached "
        "through its owner, which is named."
    ),
    "foreign": (
        "Built by a module outside the views: the sidebar, the theme picker. Named "
        "where it is defined, not here."
    ),
}

#: Modules whose widgets this test covers.
OWNED_MODULES = (
    "crapcleaner.gui.views",
    "crapcleaner.gui.dialogs",
    "crapcleaner.gui.custom_theme_builder",
)


def _exemption(widget: QWidget, root: QWidget) -> str | None:
    parent = widget.parent()
    while parent is not None and parent is not root:
        if isinstance(parent, INTERACTIVE):
            return "nested"
        module = type(parent).__module__
        if module.startswith("crapcleaner.") and not module.startswith(OWNED_MODULES):
            return "foreign"
        parent = parent.parent()
    return None


def unnamed_widgets(root: QWidget) -> list[str]:
    """Descriptions of every control under `root` with nothing to announce."""
    missing = []
    for widget in root.findChildren(QWidget):
        if not isinstance(widget, INTERACTIVE) or _exemption(widget, root):
            continue
        if (widget.accessibleName() or "").strip():
            continue
        if isinstance(widget, SELF_LABELLING) and (widget.text() or "").strip():
            continue
        hint = widget.placeholderText() if isinstance(widget, QLineEdit) else widget.toolTip()
        missing.append(f"{type(widget).__name__}({widget.objectName() or hint or '?'})")
    return missing


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def window(app):
    win = MainWindow()
    yield win
    win.close()
    win.deleteLater()


def test_every_view_names_its_controls(window):
    offenders = {}
    for key in window._PAGE_KEYS:
        window.navigate(key)
        missing = unnamed_widgets(window._views[key])
        if missing:
            offenders[key] = missing
    assert not offenders, f"controls with neither an accessible name nor a label: {offenders}"


def _group(tmp_path, count=3):
    paths = []
    for index in range(count):
        target = tmp_path / f"copy{index}.bin"
        target.write_bytes(b"x" * 16)
        paths.append(str(target))
    return DuplicateGroup(size=16, files=paths)


def test_every_dialog_names_its_controls(app, tmp_path):
    group = _group(tmp_path)
    dialogs = [
        DuplicateFilesDialog(group),
        BulkKeepRulesDialog([group]),
        ReportDialog("Report", "body"),
        ConfirmDeleteDialog("Delete", "Are you sure?"),
        RestoreRunDialog([str(tmp_path / "gone.bin")]),
    ]
    offenders = {}
    for dialog in dialogs:
        missing = unnamed_widgets(dialog)
        if missing:
            offenders[type(dialog).__name__] = missing
    for dialog in dialogs:
        dialog.deleteLater()
    assert not offenders, f"dialog controls with nothing to announce: {offenders}"


def test_exemptions_are_documented():
    """Every exemption the walk can return carries a reason someone can argue with."""
    assert set(EXEMPT_REASONS) == {"nested", "foreign"}
    for reason in EXEMPT_REASONS.values():
        assert len(reason) > 40
