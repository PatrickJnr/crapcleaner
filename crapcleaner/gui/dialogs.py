"""Custom dialogs for the CrapCleaner GUI."""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
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

#: Rule id to the label shown for it. Also the order they are offered in.
KEEP_RULES: dict[str, str] = {
    "first": "Keep First",
    "oldest": "Keep Oldest",
    "newest": "Keep Newest",
    "shortest": "Keep Shortest Path",
    "folder": "Keep the copy in a chosen folder",
}


def _mtime(path: str, missing: float) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return missing


def keep_index(paths: list[str], rule: str, folder: str = "") -> int:
    """Which copy in `paths` a keep rule spares. Always a real index."""
    if not paths:
        return -1
    if rule == "oldest":
        return min(range(len(paths)), key=lambda i: _mtime(paths[i], float("inf")))
    if rule == "newest":
        return max(range(len(paths)), key=lambda i: _mtime(paths[i], float("-inf")))
    if rule == "shortest":
        return min(range(len(paths)), key=lambda i: len(paths[i]))
    if rule == "folder" and folder:
        prefix = os.path.normcase(os.path.abspath(folder))
        for index, path in enumerate(paths):
            if os.path.normcase(os.path.abspath(path)).startswith(prefix):
                return index
    return 0


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

        sel_row = QHBoxLayout()
        sel_row.setSpacing(6)
        for rule, label in KEEP_RULES.items():
            if rule == "folder":
                continue
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, r=rule: self._apply_rule(r))
            sel_row.addWidget(button)
        btn_select_all = QPushButton("Select All")
        btn_select_all.clicked.connect(lambda: self._set_all_checked(True))
        btn_deselect_all = QPushButton("Deselect All")
        btn_deselect_all.clicked.connect(lambda: self._set_all_checked(False))
        sel_row.addWidget(btn_select_all)
        sel_row.addWidget(btn_deselect_all)
        sel_row.addStretch(1)
        layout.addLayout(sel_row)

        self.file_list = QListWidget()
        self.file_list.setAccessibleName("Copies in this duplicate group")
        for index, path in enumerate(group.files):
            item = QListWidgetItem(path)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked if index == 0 else Qt.CheckState.Checked)
            item.setToolTip(path)
            self.file_list.addItem(item)
        layout.addWidget(self.file_list, 1)

        self.keep_warning = QLabel(
            "Keep at least one copy - a group is only listed because these files are identical, "
            "so recycling every one of them removes the content itself."
        )
        self.keep_warning.setWordWrap(True)
        self.keep_warning.setProperty("danger", "true")
        self.keep_warning.setVisible(False)
        layout.addWidget(self.keep_warning)

        buttons = QDialogButtonBox()
        cancel = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        cancel.setText("Cancel")
        self.recycle_button = buttons.addButton(QDialogButtonBox.StandardButton.Ok)
        self.recycle_button.setText("Move Selected to Recycle Bin")
        self.recycle_button.setProperty("danger", "true")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Advice alone was not enough: "Select All" then confirm removed every copy.
        self.file_list.itemChanged.connect(lambda _item: self._sync_keep_state())
        self._sync_keep_state()

    def _keeps_a_copy(self) -> bool:
        """Whether at least one copy in this group is left unchecked."""
        count = self.file_list.count()
        if count == 0:
            return True
        for i in range(count):
            item = self.file_list.item(i)
            if item is not None and item.checkState() != Qt.CheckState.Checked:
                return True
        return False

    def _sync_keep_state(self) -> None:
        keeps = self._keeps_a_copy()
        self.keep_warning.setVisible(not keeps)
        self.recycle_button.setEnabled(keeps)

    def accept(self) -> None:
        # The button is disabled too, but a programmatic accept must not take the
        # last copy either.
        if not self._keeps_a_copy():
            self._sync_keep_state()
            return
        super().accept()

    def _set_all_checked(self, checked: bool):
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item is not None:
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def _apply_rule(self, rule: str):
        paths = [
            self.file_list.item(i).text()
            for i in range(self.file_list.count())
            if self.file_list.item(i) is not None
        ]
        keep = keep_index(paths, rule)
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item is not None:
                item.setCheckState(Qt.CheckState.Unchecked if i == keep else Qt.CheckState.Checked)

    def targets(self) -> list[str]:
        """Checked copies, or nothing at all if that would leave no copy behind."""
        if not self._keeps_a_copy():
            return []
        result = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                result.append(item.text())
        return result


class BulkKeepRulesDialog(QDialog):
    """Apply one keep rule to every duplicate group, previewed before it runs.

    The table behind this dialog renders only the first 150 groups; this works on
    the whole list, so groups past the cut-off are still reachable.
    """

    #: Groups listed in the preview tree. A scan can return thousands of groups and
    #: building a tree item per copy for all of them is what makes the dialog slow.
    MAX_PREVIEW_GROUPS = 200

    def __init__(self, groups, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Apply a Keep Rule to Every Group")
        self.resize(820, 600)
        self._groups = list(groups)
        self._folder = ""

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 16, 18, 16)

        header = QFrame()
        header.setProperty("card", "true")
        head_lay = QVBoxLayout(header)
        head_lay.setContentsMargins(14, 12, 14, 12)
        title = QLabel(f"{len(self._groups)} duplicate group(s)")
        title.setStyleSheet("font-size: 15px; font-weight: 700;")
        head_lay.addWidget(title)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        head_lay.addWidget(self.summary)
        layout.addWidget(header)

        rule_row = QHBoxLayout()
        rule_row.setSpacing(8)
        rule_row.addWidget(QLabel("Rule:"))
        self.rule_combo = QComboBox()
        self.rule_combo.setAccessibleName("Keep rule applied to every group")
        for rule, label in KEEP_RULES.items():
            self.rule_combo.addItem(label, rule)
        self.rule_combo.currentIndexChanged.connect(lambda _index: self._refresh())
        rule_row.addWidget(self.rule_combo, 1)

        self.folder_button = QPushButton("Choose folder…")
        self.folder_button.setToolTip("The folder whose copy is kept when a group has one.")
        self.folder_button.clicked.connect(self._choose_folder)
        rule_row.addWidget(self.folder_button)
        layout.addLayout(rule_row)

        self.folder_label = QLabel()
        self.folder_label.setWordWrap(True)
        self.folder_label.setProperty("subtle", "true")
        layout.addWidget(self.folder_label)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["File", "Outcome"])
        self.tree.setAccessibleName("Copies this rule would recycle")
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.tree, 1)

        buttons = QDialogButtonBox()
        cancel = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        cancel.setText("Cancel")
        self.recycle_button = buttons.addButton(QDialogButtonBox.StandardButton.Ok)
        self.recycle_button.setText("Move Selected to Recycle Bin")
        self.recycle_button.setProperty("danger", "true")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._refresh()

    def _rule(self) -> str:
        return str(self.rule_combo.currentData())

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Keep the copy inside this folder")
        if folder:
            self._folder = folder
            index = self.rule_combo.findData("folder")
            if index >= 0:
                self.rule_combo.setCurrentIndex(index)
            self._refresh()

    def _refresh(self):
        rule = self._rule()
        self.folder_button.setVisible(rule == "folder")
        self.folder_label.setVisible(rule == "folder")
        if rule == "folder":
            self.folder_label.setText(
                f"Keeping the copy under: {self._folder}"
                if self._folder
                else "No folder chosen yet — groups with no copy there keep their first copy."
            )

        self.tree.clear()
        total_targets = 0
        reclaimed = 0
        for position, group in enumerate(self._groups):
            paths = list(group.files)
            keep = keep_index(paths, rule, self._folder)
            targets = [p for i, p in enumerate(paths) if i != keep]
            total_targets += len(targets)
            reclaimed += group.size * len(targets)
            if position >= self.MAX_PREVIEW_GROUPS:
                continue
            parent = QTreeWidgetItem(self.tree)
            parent.setText(0, f"{len(paths)} copies · {format_size(group.size)} each")
            parent.setText(1, f"{len(targets)} to recycle")
            for index, path in enumerate(paths):
                child = QTreeWidgetItem(parent)
                child.setText(0, path)
                child.setText(1, "Kept" if index == keep else "Recycle")
                child.setToolTip(0, path)

        listed = min(len(self._groups), self.MAX_PREVIEW_GROUPS)
        hidden = len(self._groups) - listed
        hidden_note = (
            f" {hidden} more group(s) follow the same rule but are not listed." if hidden else ""
        )
        self.summary.setText(
            f"{total_targets} copy/copies would move to the Recycle Bin, freeing about "
            f"{format_size(reclaimed)}. One copy is kept in every group. "
            f"Showing {listed} group(s).{hidden_note}"
        )
        self.recycle_button.setEnabled(total_targets > 0)

    def targets(self) -> list[str]:
        """Every copy the chosen rule would recycle, across all groups."""
        rule = self._rule()
        result: list[str] = []
        for group in self._groups:
            paths = list(group.files)
            keep = keep_index(paths, rule, self._folder)
            result.extend(path for index, path in enumerate(paths) if index != keep)
        return result


class CleanupPreviewDialog(QDialog):
    """Every file a cleanup would remove, with each one deselectable.

    Unticking a file excludes that exact path from the cleanup, which is the
    difference between a listing and a preview.
    """

    def __init__(self, categories, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review Files to Clean")
        self.resize(880, 600)
        self._preview = None
        self._worker = None
        self._excluded: set[str] = set()

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 16, 18, 16)

        header = QFrame()
        header.setProperty("card", "true")
        head_lay = QVBoxLayout(header)
        head_lay.setContentsMargins(14, 12, 14, 12)
        title = QLabel("Files that will be removed")
        title.setStyleSheet("font-size: 15px; font-weight: 700;")
        head_lay.addWidget(title)
        self.summary = QLabel("Building the manifest…")
        self.summary.setWordWrap(True)
        head_lay.addWidget(self.summary)
        layout.addWidget(header)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Item", "Size"])
        self.tree.setAccessibleName("Files that will be removed")
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tree, 1)

        buttons = QDialogButtonBox()
        cancel = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        cancel.setText("Cancel")
        self.ok_button = buttons.addButton(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setText("Clean Selected Files")
        self.ok_button.setProperty("danger", "true")
        self.ok_button.setEnabled(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._start(categories)

    def _start(self, categories):
        from crapcleaner.gui.workers import PreviewWorker

        worker = PreviewWorker(categories, parent=self)
        self._worker = worker
        worker.progress.connect(
            lambda name, index, total: self.summary.setText(
                f"Scanning {name} ({index + 1}/{total})…"
            )
        )
        worker.done.connect(self._show_preview)
        worker.failed.connect(self._show_failure)
        worker.finished.connect(lambda: setattr(self, "_worker", None))
        worker.start()

    def _show_failure(self, message: str):
        self.summary.setText(f"Could not build the preview: {message}")

    def _show_preview(self, preview):
        self._preview = preview
        self.tree.blockSignals(True)
        self.tree.clear()

        for category in preview.categories:
            parent = QTreeWidgetItem(self.tree)
            parent.setText(0, category.category_name)
            parent.setText(1, format_size(category.estimated_size))
            parent.setFlags(parent.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            parent.setCheckState(0, Qt.CheckState.Checked)
            parent.setData(0, Qt.ItemDataRole.UserRole, None)

            if category.action:
                child = QTreeWidgetItem(parent)
                child.setText(0, f"Runs: {category.action}")
                child.setFlags(child.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                continue

            for item in category.items:
                child = QTreeWidgetItem(parent)
                child.setText(0, item.path)
                child.setText(1, format_size(item.size))
                child.setToolTip(0, item.path)
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                child.setCheckState(0, Qt.CheckState.Checked)
                child.setData(0, Qt.ItemDataRole.UserRole, item.path)

            if category.items_truncated:
                note = QTreeWidgetItem(parent)
                shown = len(category.items)
                note.setText(
                    0,
                    f"… and {category.item_count - shown:,} more files, not listed individually. "
                    "They are included in the cleanup.",
                )
                note.setFlags(note.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)

        self.tree.blockSignals(False)
        self.ok_button.setEnabled(True)
        self._update_summary()

    def _on_item_changed(self, item, _column):
        self.tree.blockSignals(True)
        if item.childCount():
            state = item.checkState(0)
            if state != Qt.CheckState.PartiallyChecked:
                for index in range(item.childCount()):
                    child = item.child(index)
                    if child.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                        child.setCheckState(0, state)
        parent = item.parent()
        if parent is not None:
            checked = sum(
                1
                for index in range(parent.childCount())
                if parent.child(index).checkState(0) == Qt.CheckState.Checked
            )
            checkable = sum(
                1
                for index in range(parent.childCount())
                if parent.child(index).flags() & Qt.ItemFlag.ItemIsUserCheckable
            )
            if checked == 0:
                parent.setCheckState(0, Qt.CheckState.Unchecked)
            elif checked == checkable:
                parent.setCheckState(0, Qt.CheckState.Checked)
            else:
                parent.setCheckState(0, Qt.CheckState.PartiallyChecked)
        self.tree.blockSignals(False)
        self._update_summary()

    def _walk_items(self):
        for index in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(index)
            if parent is None:
                continue
            for child_index in range(parent.childCount()):
                child = parent.child(child_index)
                if child is not None:
                    yield parent, child

    def excluded_paths(self) -> set[str]:
        """Paths the user unticked, which the cleanup must leave alone."""
        excluded = set()
        for _parent, child in self._walk_items():
            path = child.data(0, Qt.ItemDataRole.UserRole)
            if path and child.checkState(0) != Qt.CheckState.Checked:
                excluded.add(str(path))
        return excluded

    def selected_size(self) -> int:
        if self._preview is None:
            return 0
        excluded = self.excluded_paths()
        total = 0
        for category in self._preview.categories:
            total += category.estimated_size
            for item in category.items:
                if item.path in excluded:
                    total -= item.size
        return max(0, total)

    def _update_summary(self):
        if self._preview is None:
            return
        excluded = self.excluded_paths()
        listed = sum(len(c.items) for c in self._preview.categories)
        total_files = sum(c.item_count for c in self._preview.categories)
        note = ""
        if excluded:
            note = f" {len(excluded)} file(s) deselected and will be left alone."
        self.summary.setText(
            f"{total_files:,} files, {format_size(self.selected_size())} to remove. "
            f"{listed:,} listed individually.{note}"
        )


class ConfirmCleanupDialog(QDialog):
    def __init__(
        self,
        categories: list[CleanupCategory],
        dry_run_default: bool = True,
        use_recycle_bin_default: bool = True,
        parent=None,
        locked_by: list[str] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Confirm Cleanup Operation")
        self.resize(620, 520)
        self._categories = categories
        self._excluded_paths: set[str] = set()

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

        if locked_by:
            warning = QLabel(
                f"<b>{', '.join(locked_by)}</b> "
                f"{'is' if len(locked_by) == 1 else 'are'} running. Files still in use are "
                "skipped and listed in the report - close the browser first for a full clean."
            )
            warning.setWordWrap(True)
            warning.setProperty("level", "warn")
            h_lay.addWidget(warning)
        layout.addWidget(header_card)

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

        self.review_button = QPushButton("Review files…")
        self.review_button.setToolTip("List every file this cleanup would remove")
        self.review_button.clicked.connect(self._review_files)

        buttons = QDialogButtonBox()
        cancel = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        cancel.setText("Cancel")
        clean = buttons.addButton(QDialogButtonBox.StandardButton.Ok)
        clean.setText("Run Dry Run Preview" if dry_run_default else "Execute Cleanup")
        clean.setProperty("danger", not dry_run_default)
        clean.setProperty("primary", dry_run_default)
        buttons.addButton(self.review_button, QDialogButtonBox.ButtonRole.ActionRole)
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

    def _review_files(self):
        """Open the manifest, and remember anything the user unticked."""
        dialog = CleanupPreviewDialog(self._categories, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._excluded_paths = dialog.excluded_paths()
            if self._excluded_paths:
                self.review_button.setText(f"Review files… ({len(self._excluded_paths)} excluded)")

    def excluded_paths(self) -> set[str]:
        """Files the user deselected while reviewing. Empty unless they reviewed."""
        return set(getattr(self, "_excluded_paths", set()))


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


class RestoreRunDialog(QDialog):
    """Put back what one cleanup run recycled.

    Neither the Windows Recycle Bin nor the FreeDesktop trash exposes an undo we can
    drive from here, so this lists the exact paths and opens the bin rather than
    claiming a restore it cannot perform.
    """

    def __init__(self, paths: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Restore This Run")
        self.resize(760, 520)
        self._paths = list(paths)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(18, 16, 18, 16)

        card = QFrame()
        card.setProperty("card", "true")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(14, 12, 14, 12)
        title = QLabel(f"{len(self._paths)} item(s) went to the Recycle Bin")
        title.setStyleSheet("font-size: 15px; font-weight: 700;")
        card_lay.addWidget(title)
        explain = QLabel(
            "CrapCleaner cannot put these back for you: the system Recycle Bin has no "
            "restore we can call. Open it and use its own Restore command — these are "
            "the exact paths the run removed, so you can find them there."
        )
        explain.setWordWrap(True)
        card_lay.addWidget(explain)
        layout.addWidget(card)

        listing = QPlainTextEdit()
        listing.setReadOnly(True)
        listing.setPlainText("\n".join(self._paths))
        listing.setAccessibleName("Paths this run removed")
        layout.addWidget(listing, 1)

        row = QHBoxLayout()
        copy_btn = QPushButton("Copy Paths")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText("\n".join(self._paths)))
        row.addWidget(copy_btn)
        open_btn = QPushButton("Open Recycle Bin")
        open_btn.clicked.connect(self._open_bin)
        row.addWidget(open_btn)
        row.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.setProperty("primary", "true")
        close_btn.clicked.connect(self.accept)
        row.addWidget(close_btn)
        layout.addLayout(row)

    def _open_bin(self):
        import subprocess

        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", "shell:RecycleBinFolder"])
            else:
                subprocess.Popen(["xdg-open", "trash:///"])
        except (OSError, subprocess.SubprocessError):
            QApplication.beep()


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
    """Help, safety philosophy, technical documentation, and FAQ."""

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
