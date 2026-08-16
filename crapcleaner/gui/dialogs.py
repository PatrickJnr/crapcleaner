"""Custom dialogs for the CrapCleaner GUI."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.models.category import CleanupCategory
from crapcleaner.utils.format import format_size


class DuplicateFilesDialog(QDialog):
    """Let the user pick which duplicate copies to recycle (one is kept)."""

    def __init__(self, group, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review Duplicate Files")
        self.resize(720, 480)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 16, 18, 16)

        header_card = QFrame()
        header_card.setProperty("card", "true")
        h_lay = QVBoxLayout(header_card)
        h_lay.setContentsMargins(14, 12, 14, 12)

        title = QLabel(f"Duplicate Group ({len(group.files)} copies)")
        title.setStyleSheet("font-size: 15px; font-weight: 700;")
        h_lay.addWidget(title)

        intro = QLabel(
            f"File size: <b>{format_size(group.size)}</b> · "
            f"Reclaimable space: <b>{format_size(group.reclaimable)}</b>\n"
            "Checked files will be moved to the Recycle Bin. At least one original file should be kept."
        )
        intro.setWordWrap(True)
        h_lay.addWidget(intro)
        layout.addWidget(header_card)

        # Quick selection helpers
        sel_row = QHBoxLayout()
        sel_row.setSpacing(6)
        btn_keep_first = QPushButton("Keep First")
        btn_keep_first.clicked.connect(self._select_keep_first)
        btn_keep_oldest = QPushButton("Keep Oldest")
        btn_keep_oldest.clicked.connect(self._select_keep_oldest)
        btn_keep_newest = QPushButton("Keep Newest")
        btn_keep_newest.clicked.connect(self._select_keep_newest)
        btn_keep_shortest = QPushButton("Keep Shortest Path")
        btn_keep_shortest.clicked.connect(self._select_keep_shortest)
        btn_select_all = QPushButton("Select All")
        btn_select_all.clicked.connect(lambda: self._set_all_checked(True))
        btn_deselect_all = QPushButton("Deselect All")
        btn_deselect_all.clicked.connect(lambda: self._set_all_checked(False))
        sel_row.addWidget(btn_keep_first)
        sel_row.addWidget(btn_keep_oldest)
        sel_row.addWidget(btn_keep_newest)
        sel_row.addWidget(btn_keep_shortest)
        sel_row.addWidget(btn_select_all)
        sel_row.addWidget(btn_deselect_all)
        sel_row.addStretch(1)
        layout.addLayout(sel_row)

        self.file_list = QListWidget()
        for index, path in enumerate(group.files):
            item = QListWidgetItem(path)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked if index == 0 else Qt.CheckState.Checked)
            item.setToolTip(path)
            self.file_list.addItem(item)
        layout.addWidget(self.file_list, 1)

        buttons = QDialogButtonBox()
        cancel = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        cancel.setText("Cancel")
        recycle = buttons.addButton(QDialogButtonBox.StandardButton.Ok)
        recycle.setText("Move Selected to Recycle Bin")
        recycle.setProperty("danger", "true")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _set_all_checked(self, checked: bool):
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item is not None:
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def _select_keep_first(self):
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item is not None:
                item.setCheckState(Qt.CheckState.Unchecked if i == 0 else Qt.CheckState.Checked)

    def _select_keep_oldest(self):
        import os

        paths = [
            self.file_list.item(i).text()
            for i in range(self.file_list.count())
            if self.file_list.item(i) is not None
        ]
        if not paths:
            return
        mtimes = []
        for p in paths:
            try:
                mtimes.append(os.path.getmtime(p))
            except OSError:
                mtimes.append(float("inf"))
        oldest_idx = mtimes.index(min(mtimes))
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item is not None:
                item.setCheckState(
                    Qt.CheckState.Unchecked if i == oldest_idx else Qt.CheckState.Checked
                )

    def _select_keep_newest(self):
        import os

        paths = [
            self.file_list.item(i).text()
            for i in range(self.file_list.count())
            if self.file_list.item(i) is not None
        ]
        if not paths:
            return
        mtimes = []
        for p in paths:
            try:
                mtimes.append(os.path.getmtime(p))
            except OSError:
                mtimes.append(float("-inf"))
        newest_idx = mtimes.index(max(mtimes))
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item is not None:
                item.setCheckState(
                    Qt.CheckState.Unchecked if i == newest_idx else Qt.CheckState.Checked
                )

    def _select_keep_shortest(self):
        paths = [
            self.file_list.item(i).text()
            for i in range(self.file_list.count())
            if self.file_list.item(i) is not None
        ]
        if not paths:
            return
        shortest_idx = min(range(len(paths)), key=lambda i: len(paths[i]))
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item is not None:
                item.setCheckState(
                    Qt.CheckState.Unchecked if i == shortest_idx else Qt.CheckState.Checked
                )

    def targets(self) -> list[str]:
        result = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                result.append(item.text())
        return result


class ConfirmCleanupDialog(QDialog):
    def __init__(
        self,
        categories: list[CleanupCategory],
        dry_run_default: bool = True,
        use_recycle_bin_default: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Confirm Cleanup Operation")
        self.resize(620, 520)

        total = sum(c.size for c in categories)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 16, 18, 16)

        header_card = QFrame()
        header_card.setProperty("card", "true")
        h_lay = QVBoxLayout(header_card)
        h_lay.setContentsMargins(14, 12, 14, 12)

        title = QLabel(f"Selected {len(categories)} Categories for Cleanup")
        title.setStyleSheet("font-size: 15px; font-weight: 700;")
        h_lay.addWidget(title)

        intro = QLabel(
            f"Estimated space to be recovered: <b style='font-size: 14px;'>{format_size(total)}</b>"
        )
        intro.setWordWrap(True)
        h_lay.addWidget(intro)
        layout.addWidget(header_card)

        # Search filter for categories
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("Filter categories...")
        search_edit.setClearButtonEnabled(True)
        layout.addWidget(search_edit)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Category", "Safety Level", "Estimated Size"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)

        for category in categories:
            item = QTreeWidgetItem(
                [
                    category.name,
                    category.safety_level.label,
                    format_size(category.size),
                ]
            )
            item.setToolTip(0, category.description)
            self.tree.addTopLevelItem(item)

        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(1)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tree, 1)

        search_edit.textChanged.connect(self._filter_tree)

        opt_card = QFrame()
        opt_card.setProperty("card", "true")
        opt_lay = QVBoxLayout(opt_card)
        opt_lay.setContentsMargins(12, 10, 12, 10)
        opt_lay.setSpacing(6)

        self.dry_run_check = QCheckBox("Dry run — simulate scan without deleting any files")
        self.dry_run_check.setChecked(dry_run_default)
        opt_lay.addWidget(self.dry_run_check)

        self.recycle_check = QCheckBox(
            "Move files to Recycle Bin (recoverable) instead of permanent deletion"
        )
        self.recycle_check.setChecked(use_recycle_bin_default)
        self.recycle_check.setEnabled(not dry_run_default)
        opt_lay.addWidget(self.recycle_check)
        layout.addWidget(opt_card)

        buttons = QDialogButtonBox()
        cancel = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        cancel.setText("Cancel")
        clean = buttons.addButton(QDialogButtonBox.StandardButton.Ok)
        clean.setText("Run Dry Run Preview" if dry_run_default else "Execute Cleanup")
        clean.setProperty("danger", not dry_run_default)
        clean.setProperty("primary", dry_run_default)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        def on_dry_run_toggle(checked):
            clean.setText("Run Dry Run Preview" if checked else "Execute Cleanup")
            clean.setProperty("danger", not checked)
            clean.setProperty("primary", checked)
            clean.style().unpolish(clean)
            clean.style().polish(clean)
            self.recycle_check.setEnabled(not checked)

        self.dry_run_check.toggled.connect(on_dry_run_toggle)

    def _filter_tree(self, text: str):
        text = text.strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item is not None:
                match = not text or text in item.text(0).lower() or text in item.text(1).lower()
                item.setHidden(not match)

    def is_dry_run(self) -> bool:
        return self.dry_run_check.isChecked()

    def use_recycle_bin(self) -> bool:
        return self.recycle_check.isChecked()


class ReportDialog(QDialog):
    def __init__(self, title: str, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(680, 500)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 16, 18, 16)

        text_area = QPlainTextEdit()
        text_area.setReadOnly(True)
        text_area.setPlainText(text)
        text_area.setStyleSheet(
            "font-family: 'Consolas', 'Courier New', monospace; font-size: 12px;"
        )
        layout.addWidget(text_area, 1)

        btn_row = QHBoxLayout()
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(text))
        btn_row.addWidget(copy_btn)
        btn_row.addStretch(1)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)


class ConfirmDeleteDialog(QDialog):
    def __init__(self, title: str, message: str, confirm_label: str = "Delete", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(500, 180)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(18, 16, 18, 16)

        card = QFrame()
        card.setProperty("card", "true")
        c_lay = QVBoxLayout(card)
        c_lay.setContentsMargins(14, 12, 14, 12)

        label = QLabel(message)
        label.setWordWrap(True)
        label.setStyleSheet("font-size: 13px; line-height: 1.4;")
        c_lay.addWidget(label)
        layout.addWidget(card)

        buttons = QDialogButtonBox()
        cancel = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        cancel.setText("Cancel")
        ok = buttons.addButton(QDialogButtonBox.StandardButton.Ok)
        ok.setText(confirm_label)
        ok.setProperty("danger", "true")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class HelpSafetyDialog(QDialog):
    """Modal dialog displaying comprehensive Help, Safety Philosophy, Technical Documentation, and FAQ."""

    def __init__(self, main_window=None, parent=None):
        qparent = (
            parent
            if isinstance(parent, QWidget)
            else (main_window if isinstance(main_window, QWidget) else None)
        )
        super().__init__(qparent)
        self.setObjectName("HelpSafetyDialog")
        self.setWindowTitle("CrapCleaner — Help, Safety & Technical Philosophy")
        self.resize(980, 680)
        self.setMinimumSize(800, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        from crapcleaner.gui.views import HelpSafetyView

        self.help_view = HelpSafetyView(main_window, self)
        layout.addWidget(self.help_view, 1)

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(12, 0, 12, 6)

        hint = QLabel("Tip: Press F1 anytime to open this guide.")
        hint.setProperty("subtle", "true")
        hint.setStyleSheet("font-size: 11px;")
        bottom_row.addWidget(hint)
        bottom_row.addStretch(1)

        close_btn = QPushButton("Close")
        close_btn.setProperty("primary", "true")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.accept)
        bottom_row.addWidget(close_btn)
        layout.addLayout(bottom_row)

    def apply_theme(self, theme: str):
        if hasattr(self, "help_view") and hasattr(self.help_view, "apply_theme"):
            self.help_view.apply_theme(theme)
