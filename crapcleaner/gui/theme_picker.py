"""Theme Picker & Visual Gallery for CrapCleaner GUI.

Provides interactive theme cards with palette swatches, category filter chips,
real-time search, and active theme hero preview.
"""

from __future__ import annotations

import random

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.gui.icons import icon as material_icon
from crapcleaner.gui.theme import (
    THEME_CATEGORIES,
    THEMES,
    get_theme_category,
    get_theme_category_label,
    get_theme_description,
    get_theme_swatches,
    is_dark_theme,
    palette_for,
    theme_label,
)


class SwatchBar(QWidget):
    """Draws a compact row of color palette swatches with subtle borders."""

    def __init__(self, colors: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self._colors = colors
        self.setFixedHeight(14)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_colors(self, colors: list[str]) -> None:
        self._colors = colors
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        n = len(self._colors)
        if n == 0:
            return

        dot_size = 12.0
        spacing = 5.0

        for i, hex_code in enumerate(self._colors):
            x = i * (dot_size + spacing)
            y = (self.height() - dot_size) / 2.0
            rect = QRectF(x, y, dot_size, dot_size)

            col = QColor(hex_code)
            painter.setBrush(QBrush(col))
            # Subtle border around each swatch
            border_col = QColor(255, 255, 255, 60) if col.lightness() < 120 else QColor(0, 0, 0, 60)
            painter.setPen(QPen(border_col, 1))
            painter.drawRoundedRect(rect, 3.0, 3.0)


class ThemeCard(QFrame):
    """Interactive card representing a single theme with swatches, title, and active badge."""

    clicked = Signal(str)

    def __init__(self, theme_id: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.theme_id = theme_id
        self._is_active = False
        self._is_hovered = False
        self._palette = palette_for(theme_id)
        self._display_name = theme_label(theme_id)
        self._category = get_theme_category_label(theme_id)
        self._description = get_theme_description(theme_id)
        self._is_dark = is_dark_theme(theme_id)
        self._swatches = get_theme_swatches(theme_id)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(86)
        self.setMaximumHeight(96)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        self._build_ui()
        self._update_appearance()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Header: Name + Badge
        header = QHBoxLayout()
        header.setSpacing(6)

        self.title_label = QLabel(self._display_name)
        self.title_label.setTextFormat(Qt.TextFormat.PlainText)
        title_font = self.title_label.font()
        title_font.setBold(True)
        title_font.setPointSize(10)
        self.title_label.setFont(title_font)
        header.addWidget(self.title_label, 1)

        self.badge_label = QLabel(self._category)
        self.badge_label.setTextFormat(Qt.TextFormat.PlainText)
        self.badge_label.setProperty("badge", "true")
        self.badge_label.setStyleSheet(
            "font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px;"
        )
        header.addWidget(self.badge_label)

        self.active_badge = QLabel("ACTIVE")
        self.active_badge.setStyleSheet(
            "font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 4px; "
            "background-color: #22c55e; color: #ffffff;"
        )
        self.active_badge.setVisible(False)
        header.addWidget(self.active_badge)

        layout.addLayout(header)

        # Description
        self.desc_label = QLabel(self._description)
        self.desc_label.setTextFormat(Qt.TextFormat.PlainText)
        self.desc_label.setStyleSheet("font-size: 11px; color: #8c8c8c;")
        self.desc_label.setWordWrap(False)
        layout.addWidget(self.desc_label)

        # Swatch bar
        self.swatch_bar = SwatchBar(self._swatches, self)
        layout.addWidget(self.swatch_bar)

    def refresh_theme_data(self) -> None:
        """Refresh dynamic palette, labels, and swatches (e.g. for custom themes)."""
        self._palette = palette_for(self.theme_id)
        self._display_name = theme_label(self.theme_id)
        self._category = get_theme_category_label(self.theme_id)
        self._description = get_theme_description(self.theme_id)
        self._is_dark = is_dark_theme(self.theme_id)
        self._swatches = get_theme_swatches(self.theme_id)
        self.title_label.setText(self._display_name)
        self.badge_label.setText(self._category)
        self.desc_label.setText(self._description)
        self.swatch_bar.set_colors(self._swatches)
        self._update_appearance()

    def set_active(self, active: bool) -> None:
        if self._is_active != active:
            self._is_active = active
            self.active_badge.setVisible(active)
            self._update_appearance()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._is_hovered = True
        self._update_appearance()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._is_hovered = False
        self._update_appearance()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.theme_id)
        super().mousePressEvent(event)

    def _update_appearance(self) -> None:
        bg_col = self._palette.get("panel", "#1e1e1e")
        accent_col = self._palette.get("accent", "#3b82f6")
        text_col = self._palette.get("text", "#ffffff")
        muted_col = self._palette.get("muted", "#a0a0a0")

        if self._is_active:
            border = f"2px solid {accent_col}"
            shadow = f"background-color: {bg_col}; border: {border}; border-radius: 8px;"
        elif self._is_hovered:
            border = f"1px solid {accent_col}"
            shadow = f"background-color: {bg_col}; border: {border}; border-radius: 8px;"
        else:
            border = "1px solid rgba(128, 128, 128, 0.25)"
            shadow = f"background-color: {bg_col}; border: {border}; border-radius: 8px;"

        self.setStyleSheet(f"""
            ThemeCard {{
                {shadow}
            }}
        """)
        self.title_label.setStyleSheet(
            f"color: {text_col}; font-weight: 700; font-size: 12px; background: transparent; border: none;"
        )
        self.desc_label.setStyleSheet(
            f"color: {muted_col}; font-size: 11px; background: transparent; border: none;"
        )
        if not self._is_active:
            self.badge_label.setStyleSheet(
                f"color: {muted_col}; background-color: rgba(128, 128, 128, 0.15); "
                f"font-size: 10px; font-weight: 500; padding: 2px 6px; border-radius: 4px; border: none;"
            )
        else:
            self.badge_label.setStyleSheet(
                f"color: {text_col}; background-color: rgba(128, 128, 128, 0.25); "
                f"font-size: 10px; font-weight: 600; padding: 2px 6px; border-radius: 4px; border: none;"
            )


class ThemeGalleryWidget(QWidget):
    """Complete Theme Gallery component with search, category filtering,

    active hero banner, and interactive swatch card grid.
    """

    theme_changed = Signal(str)
    open_studio_requested = Signal()

    def __init__(self, current_theme: str = "dark", parent: QWidget | None = None):
        super().__init__(parent)
        self._current_theme = current_theme if current_theme in THEMES else "dark"
        self._active_category = "all"
        self._search_query = ""
        self._cards: dict[str, ThemeCard] = {}

        # Backward compatibility combo box
        self.theme_combo = QComboBox()
        for t_id in THEMES:
            self.theme_combo.addItem(theme_label(t_id), t_id)
        if self._current_theme in THEMES:
            self.theme_combo.setCurrentIndex(THEMES.index(self._current_theme))
        self.theme_combo.setVisible(False)  # Hidden behind visual gallery

        self._build_ui()
        self.select_theme(self._current_theme, emit_signal=False)

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        # 1. Active Theme Hero Banner
        self.hero_card = QFrame()
        self.hero_card.setObjectName("ActiveThemeHero")
        self.hero_card.setFrameShape(QFrame.Shape.StyledPanel)
        hero_layout = QHBoxLayout(self.hero_card)
        hero_layout.setContentsMargins(14, 10, 14, 10)
        hero_layout.setSpacing(12)

        hero_left = QVBoxLayout()
        hero_left.setSpacing(2)

        hero_title_row = QHBoxLayout()
        hero_title_row.setSpacing(8)
        hero_label_tag = QLabel("Active Theme:")
        hero_label_tag.setStyleSheet("font-size: 11px; font-weight: 600; color: #888888;")
        self.hero_name_label = QLabel(theme_label(self._current_theme))
        self.hero_name_label.setTextFormat(Qt.TextFormat.PlainText)
        self.hero_name_label.setStyleSheet("font-size: 15px; font-weight: 800;")
        self.hero_cat_badge = QLabel(get_theme_category_label(self._current_theme))
        self.hero_cat_badge.setTextFormat(Qt.TextFormat.PlainText)
        self.hero_cat_badge.setStyleSheet(
            "font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 9px; "
            "background-color: rgba(59, 130, 246, 0.2); color: #60a5fa;"
        )
        hero_title_row.addWidget(hero_label_tag)
        hero_title_row.addWidget(self.hero_name_label)
        hero_title_row.addWidget(self.hero_cat_badge)
        hero_title_row.addStretch(1)
        hero_left.addLayout(hero_title_row)

        self.hero_desc_label = QLabel(get_theme_description(self._current_theme))
        self.hero_desc_label.setTextFormat(Qt.TextFormat.PlainText)
        self.hero_desc_label.setStyleSheet("font-size: 11px; color: #999999;")
        hero_left.addWidget(self.hero_desc_label)

        self.hero_swatches = SwatchBar(get_theme_swatches(self._current_theme), self.hero_card)
        hero_left.addWidget(self.hero_swatches)

        hero_layout.addLayout(hero_left, 1)

        # Quick action buttons
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(6)

        self.studio_btn = QPushButton("Custom Studio")
        self.studio_btn.setIcon(material_icon("auto_awesome", "#ffffff"))
        self.studio_btn.setIconSize(QSize(16, 16))
        self.studio_btn.setToolTip("Open Custom Theme Studio to design your own palette")
        self.studio_btn.clicked.connect(self.open_studio_requested.emit)
        actions_layout.addWidget(self.studio_btn)

        self.random_btn = QPushButton("Surprise Me")
        self.random_btn.setIcon(material_icon("casino", "#ffffff"))
        self.random_btn.setIconSize(QSize(16, 16))
        self.random_btn.setToolTip("Switch to a random exciting theme")
        self.random_btn.clicked.connect(self._select_random_theme)
        actions_layout.addWidget(self.random_btn)

        self.reset_btn = QPushButton("Default")
        self.reset_btn.setIcon(material_icon("refresh", "#ffffff"))
        self.reset_btn.setIconSize(QSize(16, 16))
        self.reset_btn.setToolTip("Reset to Dark (default) theme")
        self.reset_btn.clicked.connect(lambda: self.select_theme("dark"))
        actions_layout.addWidget(self.reset_btn)

        hero_layout.addLayout(actions_layout)
        main_layout.addWidget(self.hero_card)

        # 2. Search & Filter Bar
        search_filter_row = QHBoxLayout()
        search_filter_row.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            f"Search {len(THEMES)} themes (e.g., retro, light, dracula, oled)..."
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_action = self.search_input.addAction(
            material_icon("search", "#888888"), QLineEdit.ActionPosition.LeadingPosition
        )
        self.search_input.textChanged.connect(self._on_search_changed)
        search_filter_row.addWidget(self.search_input, 1)

        main_layout.addLayout(search_filter_row)

        # 3. Category Filter Tabs / Chips
        self.chips_layout = QHBoxLayout()
        self.chips_layout.setSpacing(6)
        self.chip_group = QButtonGroup(self)
        self.chip_group.setExclusive(True)

        category_counts = {
            category_id: sum(
                1 for theme_id in THEMES if get_theme_category(theme_id) == category_id
            )
            for category_id in THEME_CATEGORIES
        }
        categories_def = [("all", f"All ({len(THEMES)})")] + [
            (
                category_id,
                f"{category_label} ({category_counts.get(category_id, 0)})",
            )
            for category_id, category_label in THEME_CATEGORIES.items()
        ]

        for cat_id, cat_title in categories_def:
            # Escape & as && so Qt does not render it as mnemonic accelerator / underscore
            escaped_title = cat_title.replace("&", "&&")
            btn = QPushButton(escaped_title)
            btn.setCheckable(True)
            btn.setProperty("chip", "true")
            btn.setChecked(cat_id == "all")
            btn.clicked.connect(lambda _, c=cat_id: self._on_category_selected(c))
            self.chip_group.addButton(btn)
            self.chips_layout.addWidget(btn)

        self.chips_layout.addStretch(1)
        main_layout.addLayout(self.chips_layout)

        # 4. Filter Status Label
        self.filter_status_label = QLabel(f"Showing all {len(THEMES)} themes:")
        self.filter_status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.filter_status_label.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #888888; padding-top: 2px;"
        )
        main_layout.addWidget(self.filter_status_label)

        # 5. Scroll Area & Grid of Theme Cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMinimumHeight(240)

        grid_container = QWidget()
        self.grid_layout = QGridLayout(grid_container)
        self.grid_layout.setContentsMargins(2, 2, 8, 2)
        self.grid_layout.setSpacing(8)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.grid_layout.setColumnStretch(0, 1)
        self.grid_layout.setColumnStretch(1, 1)
        self.grid_layout.setColumnStretch(2, 1)

        # No results placeholder label
        self.no_results_label = QLabel("No themes found matching your search query.")
        self.no_results_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_results_label.setStyleSheet("font-size: 13px; color: #888888; padding: 30px;")
        self.no_results_label.setVisible(False)
        self.grid_layout.addWidget(self.no_results_label, 0, 0, 1, 3)

        # Populate cards
        for theme_id in THEMES:
            card = ThemeCard(theme_id, grid_container)
            card.clicked.connect(self.select_theme)
            self._cards[theme_id] = card

        self._relayout_cards()

        scroll.setWidget(grid_container)
        main_layout.addWidget(scroll, 1)

    def _relayout_cards(self) -> None:
        """Re-arranges visible cards in a clean 3-column grid pinned to the top."""
        query = self._search_query.strip().lower()
        active_cat = self._active_category

        visible_count = 0
        columns = 3

        # Remove existing widgets from layout positions without destroying them
        for i in reversed(range(self.grid_layout.count())):
            item = self.grid_layout.itemAt(i)
            if item and item.widget() and item.widget() != self.no_results_label:
                self.grid_layout.removeItem(item)

        for theme_id, card in self._cards.items():
            matches_cat = (active_cat == "all") or (get_theme_category(theme_id) == active_cat)

            if not matches_cat:
                card.setVisible(False)
                continue

            matches_query = True
            if query:
                name = theme_label(theme_id).lower()
                desc = get_theme_description(theme_id).lower()
                cat = get_theme_category_label(theme_id).lower()
                matches_query = (
                    (query in name) or (query in theme_id) or (query in desc) or (query in cat)
                )

            if matches_query:
                card.setVisible(True)
                row = visible_count // columns
                col = visible_count % columns
                self.grid_layout.addWidget(card, row, col, Qt.AlignmentFlag.AlignTop)
                visible_count += 1
            else:
                card.setVisible(False)

        # Pin grid to top and prevent rows from stretching vertically
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        total_rows = (len(self._cards) // columns) + 3
        for r in range(total_rows):
            self.grid_layout.setRowStretch(r, 0)
        max_row = (visible_count - 1) // columns if visible_count > 0 else 0
        self.grid_layout.setRowStretch(max_row + 1, 1)

        if visible_count == 0:
            self.no_results_label.setVisible(True)
            self.filter_status_label.setText(f"No themes matching '{query}'")
        else:
            self.no_results_label.setVisible(False)
            if active_cat == "all" and not query:
                self.filter_status_label.setText(f"Showing all {visible_count} themes:")
            elif query:
                self.filter_status_label.setText(
                    f"Found {visible_count} theme(s) matching '{query}':"
                )
            else:
                cat_name = THEME_CATEGORIES.get(active_cat, active_cat)
                self.filter_status_label.setText(f"Showing {visible_count} theme(s) in {cat_name}:")

    def _on_search_changed(self, text: str) -> None:
        self._search_query = text
        self._relayout_cards()

    def _on_category_selected(self, category_id: str) -> None:
        self._active_category = category_id
        self._relayout_cards()

    def _select_random_theme(self) -> None:
        candidates = [t for t in THEMES if t != self._current_theme]
        if candidates:
            chosen = random.choice(candidates)
            self.select_theme(chosen)

    def select_theme(self, theme_id: str, emit_signal: bool = True) -> None:
        if theme_id not in THEMES:
            return

        self._current_theme = theme_id

        # Update backward-compatibility combo box
        if self.theme_combo.currentData() != theme_id:
            idx = THEMES.index(theme_id)
            self.theme_combo.blockSignals(True)
            self.theme_combo.setCurrentIndex(idx)
            self.theme_combo.blockSignals(False)

        # Update cards
        for t_id, card in self._cards.items():
            if t_id == "custom":
                card.refresh_theme_data()
            card.set_active(t_id == theme_id)

        # Update Hero Banner
        self.hero_name_label.setText(theme_label(theme_id))
        self.hero_cat_badge.setText(get_theme_category_label(theme_id))
        self.hero_desc_label.setText(get_theme_description(theme_id))
        self.hero_swatches.set_colors(get_theme_swatches(theme_id))

        # Dynamic styling for hero card based on selected theme
        pal = palette_for(theme_id)
        hero_bg = pal.get("panel", "#1c1c1c")
        hero_accent = pal.get("accent", "#3b82f6")
        hero_text = pal.get("text", "#ffffff")
        hero_muted = pal.get("muted", "#999999")
        hero_border = pal.get("border2", "#333333")

        self.hero_card.setStyleSheet(f"""
            QFrame#ActiveThemeHero {{
                background-color: {hero_bg};
                border: 1px solid {hero_border};
                border-left: 4px solid {hero_accent};
                border-radius: 8px;
            }}
        """)
        self.hero_name_label.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {hero_text}; background: transparent; border: none;"
        )
        self.hero_desc_label.setStyleSheet(
            f"font-size: 11px; color: {hero_muted}; background: transparent; border: none;"
        )

        # Update action buttons and search icon colors
        self.random_btn.setIcon(material_icon("casino", hero_text))
        self.reset_btn.setIcon(material_icon("refresh", hero_text))
        if hasattr(self, "search_action"):
            self.search_action.setIcon(material_icon("search", hero_muted))

        if emit_signal:
            self.theme_changed.emit(theme_id)

    def current_theme(self) -> str:
        return self._current_theme
