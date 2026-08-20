"""Cleanup view: category tree, scan results, and cleanup controls."""

import os

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.gui.icons import icon as material_icon
from crapcleaner.gui.views.common import _c, _safety_color, _SizeSortedItem, page_header
from crapcleaner.history import last_cleaned, regrowth_estimate
from crapcleaner.models.category import SafetyLevel
from crapcleaner.utils.files import file_manager_name, reveal_in_file_manager
from crapcleaner.utils.format import (
    format_datetime,
    format_size,
)

#: Read as "not enough history": one cleanup tells you nothing about a rate.
NOT_ENOUGH_HISTORY = "not enough history yet"


def regrowth_text(category_id: str) -> str:
    """How fast a category comes back, phrased as a rate rather than a total."""
    last = last_cleaned(category_id)
    rate = regrowth_estimate(category_id)
    when = f"last cleaned {format_datetime(last)}" if last else "never cleaned here"
    if rate is None:
        return f"{when} · regrowth: {NOT_ENOUGH_HISTORY}"
    return f"{when} · regrows about {format_size(int(rate))} per week"


class CleanupView(QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self._main = main
        self._categories: list = []
        self._scanning = False
        self._theme = "dark"
        self._touched = set()
        self._last_checked = set()
        self._safety_filter = "ALL"
        self._sort_descending = True
        self._current_explained_category = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(10)
        layout.addWidget(
            page_header(
                "Cleanup Manager",
                "Select categories to clean. Safe items are pre-selected. Dangerous categories are protected.",
            )
        )

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.scan_button = QPushButton("Scan Now")
        self.scan_button.setProperty("primary", "true")
        self.scan_button.setIcon(material_icon("search", "#ffffff"))
        self.scan_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_button.clicked.connect(self._main.start_scan)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.hide()
        self.cancel_button.clicked.connect(
            lambda: (
                self._main.cancel_active_scan()
                if hasattr(self._main, "cancel_active_scan")
                else None
            )
        )

        self.safe_button = QPushButton("Select Safe")
        self.safe_button.setIcon(material_icon("security", _c(self._theme, "text")))
        self.safe_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.safe_button.clicked.connect(lambda: self._select_by_safety(True))

        self.all_button = QPushButton("Select All")
        self.all_button.setIcon(material_icon("done_all", _c(self._theme, "text")))
        self.all_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.all_button.clicked.connect(lambda: self._select_all(True))

        self.none_button = QPushButton("Deselect All")
        self.none_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.none_button.clicked.connect(lambda: self._select_all(False))

        self.invert_button = QPushButton("Invert")
        self.invert_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.invert_button.clicked.connect(self._invert_selection)

        toolbar.addWidget(self.scan_button)
        toolbar.addWidget(self.cancel_button)
        toolbar.addWidget(self.safe_button)
        toolbar.addWidget(self.all_button)
        toolbar.addWidget(self.none_button)
        toolbar.addWidget(self.invert_button)
        toolbar.addStretch(1)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search categories (Ctrl+F)...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedWidth(220)
        self.search_edit.setAccessibleName("Search cleanup categories")
        self.search_edit.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self.search_edit)
        layout.addLayout(toolbar)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)

        self._chip_buttons = {}
        chips = [
            ("ALL", "All"),
            ("SAFE", "Safe Only"),
            ("LOW_RISK", "Low Risk"),
            ("REVIEW", "Review Required"),
            ("ADMIN", "Requires Admin"),
        ]
        for key, text in chips:
            btn = QPushButton(text)
            btn.setProperty("chip", "true")
            btn.setProperty("active", "true" if key == "ALL" else "false")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self._set_safety_filter(k))
            filter_row.addWidget(btn)
            self._chip_buttons[key] = btn

        filter_row.addStretch(1)

        sort_btn = QPushButton("Sort by Size")
        sort_btn.setProperty("ghost", "true")
        sort_btn.setToolTip("Order categories by how much space they can reclaim.")
        sort_btn.clicked.connect(lambda: self.sort_by_size(not self._sort_descending))
        filter_row.addWidget(sort_btn)

        exp_btn = QPushButton("Expand All")
        exp_btn.setProperty("ghost", "true")
        exp_btn.clicked.connect(self.tree_expand_all)
        col_btn = QPushButton("Collapse All")
        col_btn.setProperty("ghost", "true")
        col_btn.clicked.connect(self.tree_collapse_all)
        filter_row.addWidget(exp_btn)
        filter_row.addWidget(col_btn)

        layout.addLayout(filter_row)

        shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        shortcut.activated.connect(self.search_edit.setFocus)

        tree_card = QFrame()
        tree_card.setProperty("card", "true")
        tree_card_lay = QVBoxLayout(tree_card)
        tree_card_lay.setContentsMargins(8, 8, 8, 8)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Category", "Safety Level", "Item Count", "Reclaimable Size"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setIndentation(18)
        self.tree.setAccessibleName("Cleanup categories")
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_tree_menu)
        self.tree.itemClicked.connect(self._on_group_clicked)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.currentItemChanged.connect(self._on_current_item_changed)
        tree_card_lay.addWidget(self.tree)
        layout.addWidget(tree_card, 1)

        summary_card = QFrame()
        summary_card.setProperty("card", "true")
        summary_lay = QHBoxLayout(summary_card)
        summary_lay.setContentsMargins(18, 12, 18, 12)
        summary_lay.setSpacing(12)

        self.clean_button = QPushButton("Clean Selected")
        self.clean_button.setProperty("danger", "true")
        self.clean_button.setIcon(material_icon("clean", "#ffffff"))
        self.clean_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clean_button.setEnabled(False)
        self.clean_button.setFixedHeight(36)
        self.clean_button.setFixedWidth(160)
        self.clean_button.clicked.connect(self._main.clean_selected)
        summary_lay.addWidget(self.clean_button)

        self.summary_label = QLabel("Run a scan to calculate reclaimable space.")
        self.summary_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        summary_lay.addWidget(self.summary_label, 1)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(8)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(180)
        self.progress_bar.setVisible(False)
        self.progress_bar.setAccessibleName("Cleanup progress")
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {_c(self._theme, 'muted')}; font-size: 12px;")
        progress_row.addWidget(self.progress_bar)
        progress_row.addWidget(self.status_label)
        summary_lay.addLayout(progress_row)

        layout.addWidget(summary_card)

        self.scan_delta_label = QLabel("Run a scan to compare it with the previous one.")
        self.scan_delta_label.setWordWrap(True)
        self.scan_delta_label.setProperty("subtle", "true")
        layout.addWidget(self.scan_delta_label)

        explain_card = QFrame()
        explain_card.setProperty("card", "true")
        explain_lay = QVBoxLayout(explain_card)
        explain_lay.setContentsMargins(14, 12, 14, 12)
        explain_lay.setSpacing(6)
        explain_title = QLabel("Why is this here?")
        explain_title.setStyleSheet("font-size: 14px; font-weight: 700;")
        explain_lay.addWidget(explain_title)
        self.explain_label = QLabel(
            "Select a cleanup category to see what it contains, why it grows, why it is safe to remove, and what will be regenerated."
        )
        self.explain_label.setWordWrap(True)
        self.explain_label.setProperty("subtle", "true")
        explain_lay.addWidget(self.explain_label)
        layout.addWidget(explain_card)

    def tree_expand_all(self):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item is not None:
                item.setExpanded(True)

    def tree_collapse_all(self):
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item is not None:
                item.setExpanded(False)

    def _set_safety_filter(self, filter_key: str):
        self._safety_filter = filter_key
        for k, btn in self._chip_buttons.items():
            active = k == filter_key
            btn.setProperty("active", "true" if active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._apply_filter(self.search_edit.text())

    def _show_tree_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        category = item.data(0, Qt.ItemDataRole.UserRole)
        menu = QMenu(self)

        if category is not None:
            toggle_action = menu.addAction("Toggle Selection")
            copy_action = menu.addAction("Copy Category Name")
            open_folder_action = None
            if category.targets:
                first_target = category.targets[0].path
                if os.path.exists(first_target):
                    open_folder_action = menu.addAction(f"Open Target in {file_manager_name()}")

            action = menu.exec(self.tree.viewport().mapToGlobal(pos))
            if action == toggle_action and (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                cur = item.checkState(0)
                item.setCheckState(
                    0,
                    (
                        Qt.CheckState.Unchecked
                        if cur == Qt.CheckState.Checked
                        else Qt.CheckState.Checked
                    ),
                )
            elif action == copy_action:
                QApplication.clipboard().setText(category.name)
            elif open_folder_action and action == open_folder_action:
                target_path = category.targets[0].path
                if os.path.isdir(target_path):
                    reveal_in_file_manager(target_path, select=False)
                else:
                    reveal_in_file_manager(target_path)

    def _set_children_checked(self, group_item, checked: bool):
        self.tree.blockSignals(True)
        try:
            for j in range(group_item.childCount()):
                child = group_item.child(j)
                if not (child.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                    continue
                child.setCheckState(
                    0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
                )
        finally:
            self.tree.blockSignals(False)

    def _on_current_item_changed(self, item, _previous):
        category = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
        self._current_explained_category = category
        if category is None:
            self.explain_label.setText(
                "Select a cleanup category to see what it contains, why it grows, why it is safe to remove, and what will be regenerated."
            )
            return
        parts = [f"<b>{category.name}</b>", category.description]
        if category.what_it_contains:
            parts.append(f"<b>Contains:</b> {category.what_it_contains}")
        if category.why_it_grows:
            parts.append(f"<b>Why it grows:</b> {category.why_it_grows}")
        if category.why_safe_to_delete:
            parts.append(f"<b>Why safe to delete:</b> {category.why_safe_to_delete}")
        if category.regeneration_behavior:
            parts.append(f"<b>After cleanup:</b> {category.regeneration_behavior}")
        if category.requires_admin:
            parts.append("<b>Permission:</b> Requires administrator privileges.")
        if not category.reversible:
            parts.append("<b>Reversibility:</b> This action is not reversible.")
        # Read on selection rather than per row: each lookup re-reads the history log.
        parts.append(f"<b>History:</b> {regrowth_text(category.id)}")
        self.explain_label.setText("<br><br>".join(parts))

    def set_scan_delta(self, previous_snapshot, current_snapshot):
        if not previous_snapshot:
            self.scan_delta_label.setText("Run a scan to compare it with the previous one.")
            return
        previous_total = int(previous_snapshot.get("total_identified", 0) or 0)
        if not current_snapshot:
            self.scan_delta_label.setText(
                f"Last scan found {format_size(previous_total)} reclaimable. Run another scan to see what changed."
            )
            return
        current_total = int(current_snapshot.get("total_identified", 0) or 0)
        delta = current_total - previous_total
        prev_categories = previous_snapshot.get("categories", {}) or {}
        curr_categories = current_snapshot.get("categories", {}) or {}
        changes = []
        for category in self._categories:
            before = int(prev_categories.get(category.id, 0) or 0)
            after = int(curr_categories.get(category.id, 0) or 0)
            diff = after - before
            if diff > 0:
                changes.append((diff, category.name))
        changes.sort(reverse=True)
        if delta > 0:
            headline = f"Since the last scan: reclaimable space increased by {format_size(delta)}."
        elif delta < 0:
            headline = (
                f"Since the last scan: reclaimable space decreased by {format_size(abs(delta))}."
            )
        else:
            headline = "Since the last scan: total reclaimable space is unchanged."
        if changes:
            top = ", ".join(f"{name} (+{format_size(diff)})" for diff, name in changes[:3])
            headline += f" Biggest growth: {top}."
        self.scan_delta_label.setText(headline)

    def _on_group_clicked(self, item, column):
        if column != 0:
            return
        if item.data(0, Qt.ItemDataRole.UserRole) is not None or item.childCount() == 0:
            return
        checked = item.checkState(0) == Qt.CheckState.Checked
        self._set_children_checked(item, checked)
        self._sync_group_state(item)
        self._update_summary()

    def _on_item_changed(self, item: QTreeWidgetItem, column: int):
        if column != 0:
            return
        if item.data(0, Qt.ItemDataRole.UserRole) is None:
            return
        category = item.data(0, Qt.ItemDataRole.UserRole)
        self._touched.add(category.id)
        if item.checkState(0) == Qt.CheckState.Checked:
            self._last_checked.add(category.id)
        else:
            self._last_checked.discard(category.id)
        parent = item.parent()
        if parent is not None:
            self._sync_group_state(parent)
        self._update_summary()

    def _sync_group_state(self, group_item):
        checked = unchecked = 0
        for j in range(group_item.childCount()):
            child = group_item.child(j)
            if not (child.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                continue
            state = child.checkState(0)
            if state == Qt.CheckState.Checked:
                checked += 1
            elif state == Qt.CheckState.Unchecked:
                unchecked += 1
            else:
                group_item.setCheckState(0, Qt.CheckState.PartiallyChecked)
                return
        if checked and not unchecked:
            group_item.setCheckState(0, Qt.CheckState.Checked)
        elif unchecked and not checked:
            group_item.setCheckState(0, Qt.CheckState.Unchecked)
        else:
            group_item.setCheckState(0, Qt.CheckState.PartiallyChecked)

    def _select_by_safety(self, recommended_only: bool = False):
        self.tree.blockSignals(True)
        try:
            for i in range(self.tree.topLevelItemCount()):
                group = self.tree.topLevelItem(i)
                if group is None:
                    continue
                for j in range(group.childCount()):
                    child = group.child(j)
                    if child is None:
                        continue
                    category = child.data(0, Qt.ItemDataRole.UserRole)
                    if category is None:
                        continue
                    if recommended_only:
                        check = (
                            category.safety_level in (SafetyLevel.SAFE, SafetyLevel.LOW_RISK)
                            and category.selected_by_default
                        )
                    else:
                        check = True
                    child.setCheckState(
                        0, Qt.CheckState.Checked if check else Qt.CheckState.Unchecked
                    )
                self._sync_group_state(group)
        finally:
            self.tree.blockSignals(False)
        self._update_summary()

    def _select_all(self, selected: bool):
        for category in self._categories:
            if category.safety_level != SafetyLevel.DANGEROUS:
                self._set_category_checked(category, selected)

    def _invert_selection(self):
        self.tree.blockSignals(True)
        try:
            for i in range(self.tree.topLevelItemCount()):
                group = self.tree.topLevelItem(i)
                if group is None:
                    continue
                for j in range(group.childCount()):
                    child = group.child(j)
                    if child is not None and (child.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                        cur = child.checkState(0)
                        child.setCheckState(
                            0,
                            (
                                Qt.CheckState.Unchecked
                                if cur == Qt.CheckState.Checked
                                else Qt.CheckState.Checked
                            ),
                        )
                self._sync_group_state(group)
        finally:
            self.tree.blockSignals(False)
        self._update_summary()

    def review_recommended(self):
        """Pre-check the safe and low-risk categories, leaving dangerous ones locked."""
        self._select_by_safety(True)
        self.tree.scrollToTop()

    def _set_category_checked(self, category, checked: bool):
        item = self._item_for_category(category)
        if item is not None:
            item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def _item_for_category(self, category):
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            if group is None:
                continue
            for j in range(group.childCount()):
                child = group.child(j)
                if child is not None and child.data(0, Qt.ItemDataRole.UserRole) is category:
                    return child
        return None

    def _find_category_item(self, name: str):
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            if group is None:
                continue
            for j in range(group.childCount()):
                child = group.child(j)
                if child is not None:
                    category = child.data(0, Qt.ItemDataRole.UserRole)
                    if category is not None and category.name == name:
                        return child
        return None

    def sort_by_size(self, descending: bool = True):
        """Order every group, and the categories inside it, by reclaimable size."""
        self._sort_descending = descending
        order = Qt.SortOrder.DescendingOrder if descending else Qt.SortOrder.AscendingOrder
        self.tree.sortItems(3, order)
        for index in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(index)
            if group is not None:
                group.sortChildren(3, order)

    def populate(self, categories):
        self._categories = categories
        self.tree.blockSignals(True)
        try:
            self.tree.clear()
            groups: dict = {}
            for category in categories:
                groups.setdefault(category.group, []).append(category)

            for group_name, members in groups.items():
                group_item = _SizeSortedItem([group_name])
                group_item.setFlags(
                    group_item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable & ~Qt.ItemFlag.ItemIsAutoTristate
                )
                group_item.setCheckState(0, Qt.CheckState.Unchecked)
                for category in members:
                    safety = category.safety_level
                    item = _SizeSortedItem()
                    item.setText(1, safety.label)
                    item.setText(2, str(category.item_count) if category.item_count else "")
                    item.setText(3, format_size(category.size) if category.size else "")
                    item.set_sort_size(category.size)
                    color = QColor(_safety_color(self._theme, safety))
                    item.setForeground(1, color)
                    item.setToolTip(0, category.description)
                    item.setToolTip(1, category.description)
                    item.setData(0, Qt.ItemDataRole.UserRole, category)
                    if safety == SafetyLevel.DANGEROUS:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
                        item.setForeground(0, QColor(_c(self._theme, "danger")))
                        item.setCheckState(0, Qt.CheckState.Unchecked)
                    else:
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        if category.id in self._touched:
                            state = (
                                Qt.CheckState.Checked
                                if category.id in self._last_checked
                                else Qt.CheckState.Unchecked
                            )
                        else:
                            state = (
                                Qt.CheckState.Checked
                                if category.selected_by_default and category.size > 0
                                else Qt.CheckState.Unchecked
                            )
                        item.setCheckState(0, state)
                    item.setText(
                        0,
                        category.name + ("  [requires admin]" if category.requires_admin else ""),
                    )
                    group_item.addChild(item)
                self._sync_group_state(group_item)
                self.tree.addTopLevelItem(group_item)
                group_item.setExpanded(True)
        finally:
            self.tree.blockSignals(False)
        self._apply_filter(self.search_edit.text() if hasattr(self, "search_edit") else "")
        for col in range(4):
            self.tree.resizeColumnToContents(col)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._update_summary()

    def _auto_check_defaults(self):
        updated_groups = set()
        self.tree.blockSignals(True)
        try:
            for i in range(self.tree.topLevelItemCount()):
                group = self.tree.topLevelItem(i)
                if group is None:
                    continue
                for j in range(group.childCount()):
                    child = group.child(j)
                    if child is None:
                        continue
                    category = child.data(0, Qt.ItemDataRole.UserRole)
                    if category is None or category.id in self._touched:
                        continue
                    if (
                        category.selected_by_default
                        and category.size > 0
                        and child.checkState(0) != Qt.CheckState.Checked
                    ):
                        child.setCheckState(0, Qt.CheckState.Checked)
                        updated_groups.add(group)
        finally:
            self.tree.blockSignals(False)
        for group in updated_groups:
            self._sync_group_state(group)

    def update_sizes(self):
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            if group is None:
                continue
            group_total = 0
            for j in range(group.childCount()):
                child = group.child(j)
                if child is None:
                    continue
                category = child.data(0, Qt.ItemDataRole.UserRole)
                if category is None:
                    continue
                child.setText(2, str(category.item_count) if category.item_count else "")
                child.setText(3, format_size(category.size) if category.size else "")
                if hasattr(child, "set_sort_size"):
                    child.set_sort_size(category.size)
                group_total += category.size
            group.setText(2, f"{group.childCount()} categories")
            group.setText(3, format_size(group_total) if group_total else "")
            if hasattr(group, "set_sort_size"):
                group.set_sort_size(group_total)
        self._auto_check_defaults()
        for col in range(4):
            self.tree.resizeColumnToContents(col)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._update_summary()

    def selected_categories(self):
        selected = []
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            if group is None:
                continue
            for j in range(group.childCount()):
                child = group.child(j)
                if child is not None and child.checkState(0) == Qt.CheckState.Checked:
                    category = child.data(0, Qt.ItemDataRole.UserRole)
                    if category is not None:
                        selected.append(category)
        return selected

    def _apply_filter(self, text: str):
        text = (text or "").strip().lower()
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            if group is None:
                continue
            visible = 0
            for j in range(group.childCount()):
                child = group.child(j)
                if child is None:
                    continue
                cat = child.data(0, Qt.ItemDataRole.UserRole)
                match_text = (
                    not text or text in child.text(0).lower() or text in child.text(1).lower()
                )

                match_safety = True
                if self._safety_filter == "SAFE":
                    match_safety = cat is not None and cat.safety_level == SafetyLevel.SAFE
                elif self._safety_filter == "LOW_RISK":
                    match_safety = cat is not None and cat.safety_level == SafetyLevel.LOW_RISK
                elif self._safety_filter == "REVIEW":
                    match_safety = cat is not None and cat.safety_level == SafetyLevel.REVIEW
                elif self._safety_filter == "ADMIN":
                    match_safety = cat is not None and cat.requires_admin

                match = match_text and match_safety
                child.setHidden(not match)
                if match:
                    visible += 1
            group.setHidden(visible == 0)

    def _update_summary(self):
        selected = self.selected_categories()
        total = sum(c.size for c in selected)
        self.clean_button.setEnabled(bool(selected) and total > 0)
        self.summary_label.setText(
            f"<b>{len(selected)} categories</b> selected — Estimated space recovery: "
            f"<b style='color: {_c(self._theme, 'accent')};'>{format_size(total)}</b>"
        )

    def set_scanning(self, scanning: bool):
        self._scanning = scanning
        self.scan_button.setEnabled(not scanning)
        self.cancel_button.setVisible(scanning)
        if scanning:
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setVisible(True)
            self.status_label.setText("Scanning categories...")
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.progress_bar.setVisible(False)
            self.status_label.setText("")

    def highlight_category(self, name: str):
        self.clear_highlight()
        item = self._find_category_item(name)
        if item is None:
            return
        base = QColor(_c(self._theme, "selection"))
        base.setAlpha(50)
        for col in range(self.tree.columnCount()):
            item.setBackground(col, QBrush(base))
        self.tree.scrollToItem(item)

    def clear_highlight(self):
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            if group is None:
                continue
            for j in range(group.childCount()):
                child = group.child(j)
                if child is not None:
                    for col in range(self.tree.columnCount()):
                        child.setBackground(col, QBrush())

    def set_cleaning(self, cleaning: bool, total: int = 1):
        self.clean_button.setEnabled(not cleaning)
        if cleaning:
            self.progress_bar.setRange(0, max(total, 1))
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)

    def set_clean_progress(self, name: str, index: int):
        self.progress_bar.setValue(index)
        self.status_label.setText(f"Cleaning: {name}")

    def clear_status(self):
        self.progress_bar.setVisible(False)
        self.status_label.setText("")

    def apply_theme(self, theme: str):
        self._theme = theme
        self.status_label.setStyleSheet(f"color: {_c(theme, 'muted')};")
