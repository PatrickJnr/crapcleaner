"""Custom Theme Studio & Builder Widget for CrapCleaner GUI.

Allows users to pick a signature primary color, select palette mood styles
(Cohesive, Vibrant, Muted, OLED, Pastel, Minimal), switch between Dark, Light,
and OLED canvases, generate harmonious palettes with a magic dice, fine-tune
contrast and vibrancy, and preview live multi-tab UI mockups before saving.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.gui.color_engine import (
    contrast_ratio,
    ensure_contrast,
    export_custom_theme_json,
    generate_custom_palette,
    generate_magic_palette,
    import_custom_theme_json,
    normalize_hex,
)
from crapcleaner.gui.icons import icon as material_icon

# ---------------------------------------------------------------------------
# 15 Curated Designer Color Presets
# ---------------------------------------------------------------------------
PRESET_COLORS = [
    ("Sapphire Blue", "#3b82f6"),
    ("Emerald Forest", "#10b981"),
    ("Cyber Violet", "#8b5cf6"),
    ("Sunset Amber", "#f59e0b"),
    ("Crimson Velvet", "#dc2626"),
    ("Rose Gold", "#f43f5e"),
    ("Hyper Cyan", "#06b6d4"),
    ("Deep Slate", "#64748b"),
    ("Mint Sage", "#14b8a6"),
    ("Solar Orange", "#f97316"),
    ("Royal Indigo", "#6366f1"),
    ("Cherry Blossom", "#ec4899"),
    ("Arctic Frost", "#38bdf8"),
    ("Matrix Lime", "#84cc16"),
    ("Espresso Gold", "#d97706"),
]


class LiveThemePreviewCard(QFrame):
    """Interactive visual preview with tabbed mockups (Overview, Table, Palette Matrix)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._palette: dict[str, str] = {}
        self._primary_color: str = "#3b82f6"
        self._mode: str = "dark"
        self._mood: str = "cohesive"
        self._preview_tab_buttons: dict[str, QPushButton] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 12, 14, 12)
        self.main_layout.setSpacing(10)

        # 1. Header with Title, Mode Badges & View Switcher
        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        self.preview_title = QLabel("Live Theme Preview")
        self.preview_title.setTextFormat(Qt.TextFormat.PlainText)
        t_font = self.preview_title.font()
        t_font.setBold(True)
        t_font.setPointSize(11)
        self.preview_title.setFont(t_font)
        header_row.addWidget(self.preview_title)

        self.mode_badge = QLabel("DARK MODE")
        self.mode_badge.setTextFormat(Qt.TextFormat.PlainText)
        self.mode_badge.setStyleSheet(
            "font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 4px;"
        )
        header_row.addWidget(self.mode_badge)

        self.cr_badge = QLabel("CONTRAST: AAA")
        self.cr_badge.setTextFormat(Qt.TextFormat.PlainText)
        self.cr_badge.setStyleSheet(
            "font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 4px;"
        )
        header_row.addWidget(self.cr_badge)

        header_row.addStretch(1)

        # Sub-view switcher tabs inside preview
        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)

        for tab_key, tab_label in [
            ("overview", "Overview"),
            ("table", "Table View"),
            ("matrix", "Palette Matrix"),
        ]:
            btn = QPushButton(tab_label)
            btn.setCheckable(True)
            btn.setProperty("chip", "true")
            btn.setChecked(tab_key == "overview")
            btn.setFixedHeight(22)
            btn.setStyleSheet("font-size: 9px; padding: 2px 8px;")
            btn.clicked.connect(lambda _, k=tab_key: self._set_preview_view(k))
            self.tab_group.addButton(btn)
            self._preview_tab_buttons[tab_key] = btn
            header_row.addWidget(btn)

        self.main_layout.addLayout(header_row)

        # 2. Stacked Preview Views
        self.preview_stack = QStackedWidget()

        # VIEW A: Mockup Overview (Cards, Badges, Action Buttons)
        page_overview = QWidget()
        ov_lay = QVBoxLayout(page_overview)
        ov_lay.setContentsMargins(0, 0, 0, 0)
        ov_lay.setSpacing(8)

        grid = QGridLayout()
        grid.setSpacing(8)

        # Mock Stat Card
        self.stat_box = QFrame()
        stat_lay = QVBoxLayout(self.stat_box)
        stat_lay.setContentsMargins(10, 8, 10, 8)
        stat_lay.setSpacing(2)

        self.stat_title = QLabel("CLEANUP CANDIDATES")
        self.stat_title.setTextFormat(Qt.TextFormat.PlainText)
        self.stat_title.setStyleSheet("font-size: 9px; font-weight: 700; letter-spacing: 0.5px;")
        self.stat_val = QLabel("6.42 GB")
        self.stat_val.setTextFormat(Qt.TextFormat.PlainText)
        val_font = self.stat_val.font()
        val_font.setBold(True)
        val_font.setPointSize(13)
        self.stat_val.setFont(val_font)

        self.stat_sub = QLabel("5,280 items ready to purge safely")
        self.stat_sub.setTextFormat(Qt.TextFormat.PlainText)
        self.stat_sub.setStyleSheet("font-size: 10px;")

        stat_lay.addWidget(self.stat_title)
        stat_lay.addWidget(self.stat_val)
        stat_lay.addWidget(self.stat_sub)
        grid.addWidget(self.stat_box, 0, 0, 1, 2)

        # Mock System Status Badges Card
        self.badges_box = QFrame()
        badges_lay = QVBoxLayout(self.badges_box)
        badges_lay.setContentsMargins(10, 8, 10, 8)
        badges_lay.setSpacing(4)

        b_title = QLabel("SYSTEM SAFETY RATINGS")
        b_title.setTextFormat(Qt.TextFormat.PlainText)
        b_title.setStyleSheet("font-size: 9px; font-weight: 700; letter-spacing: 0.5px;")
        badges_lay.addWidget(b_title)

        pills_row = QHBoxLayout()
        pills_row.setSpacing(6)
        self.badge_safe = QLabel("SAFE")
        self.badge_safe.setTextFormat(Qt.TextFormat.PlainText)
        self.badge_warn = QLabel("WARNING")
        self.badge_warn.setTextFormat(Qt.TextFormat.PlainText)
        self.badge_danger = QLabel("CRITICAL")
        self.badge_danger.setTextFormat(Qt.TextFormat.PlainText)
        for b in (self.badge_safe, self.badge_warn, self.badge_danger):
            b.setStyleSheet(
                "font-size: 8px; font-weight: 700; padding: 2px 5px; border-radius: 4px;"
            )
            pills_row.addWidget(b)
        pills_row.addStretch(1)
        badges_lay.addLayout(pills_row)

        grid.addWidget(self.badges_box, 0, 2, 1, 2)
        ov_lay.addLayout(grid)

        # Mock Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.mock_primary_btn = QPushButton("Clean Junk")
        self.mock_primary_btn.setFixedHeight(26)
        self.mock_primary_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self.mock_secondary_btn = QPushButton("Deep Scan")
        self.mock_secondary_btn.setFixedHeight(26)

        self.mock_danger_btn = QPushButton("Purge All")
        self.mock_danger_btn.setFixedHeight(26)

        btn_row.addWidget(self.mock_primary_btn)
        btn_row.addWidget(self.mock_secondary_btn)
        btn_row.addWidget(self.mock_danger_btn)
        btn_row.addStretch(1)
        ov_lay.addLayout(btn_row)

        # Swatch Mini Bar
        self.swatch_container = QFrame()
        swatch_lay = QHBoxLayout(self.swatch_container)
        swatch_lay.setContentsMargins(6, 4, 6, 4)
        swatch_lay.setSpacing(4)

        self.swatch_labels: list[tuple[str, QLabel]] = []
        tokens = [
            ("Primary", "accent"),
            ("Window", "window"),
            ("Surface", "surface"),
            ("Text", "text"),
            ("Success", "success"),
            ("Warning", "warning"),
            ("Danger", "danger"),
        ]
        for name, key in tokens:
            pill = QLabel(f"{name}")
            pill.setTextFormat(Qt.TextFormat.PlainText)
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pill.setStyleSheet(
                "font-size: 8px; font-weight: 700; padding: 2px 4px; border-radius: 3px;"
            )
            swatch_lay.addWidget(pill)
            self.swatch_labels.append((key, pill))

        ov_lay.addWidget(self.swatch_container)
        self.preview_stack.addWidget(page_overview)

        # VIEW B: Table & List View Mockup
        page_table = QWidget()
        tbl_lay = QVBoxLayout(page_table)
        tbl_lay.setContentsMargins(0, 0, 0, 0)
        self.mock_table = QTableWidget(3, 3)
        self.mock_table.setHorizontalHeaderLabels(["Target Path", "Size", "Risk Level"])
        self.mock_table.horizontalHeader().setStretchLastSection(True)
        self.mock_table.verticalHeader().setVisible(False)
        self.mock_table.setFixedHeight(120)
        self.mock_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        rows_data = [
            ("C:/Windows/Temp/*", "1.82 GB", "Safe"),
            ("~/.cache/pip/wheels", "640 MB", "Safe"),
            ("~/AppData/Local/CrashDumps", "3.96 GB", "Review"),
        ]
        for r, (p_path, p_size, p_risk) in enumerate(rows_data):
            self.mock_table.setItem(r, 0, QTableWidgetItem(p_path))
            self.mock_table.setItem(r, 1, QTableWidgetItem(p_size))
            self.mock_table.setItem(r, 2, QTableWidgetItem(p_risk))
        tbl_lay.addWidget(self.mock_table)
        self.preview_stack.addWidget(page_table)

        # VIEW C: 27-Token Palette Matrix
        page_matrix = QWidget()
        mat_lay = QVBoxLayout(page_matrix)
        mat_lay.setContentsMargins(0, 0, 0, 0)
        self.matrix_grid = QGridLayout()
        self.matrix_grid.setSpacing(4)
        self.matrix_chips: dict[str, tuple[QFrame, QLabel, QLabel]] = {}

        matrix_tokens = [
            "window",
            "panel",
            "surface",
            "surface2",
            "elevated",
            "border",
            "text",
            "muted",
            "accent",
            "accent_hover",
            "success",
            "warning",
            "danger",
            "info",
            "review",
        ]
        for idx, token_name in enumerate(matrix_tokens):
            row, col = divmod(idx, 5)
            chip_frame = QFrame()
            chip_frame.setFixedHeight(26)
            chip_lay = QHBoxLayout(chip_frame)
            chip_lay.setContentsMargins(4, 2, 4, 2)
            chip_lay.setSpacing(4)

            t_name_lbl = QLabel(token_name)
            t_name_lbl.setTextFormat(Qt.TextFormat.PlainText)
            t_name_lbl.setStyleSheet("font-size: 8px; font-weight: 700;")

            hex_val_lbl = QLabel("#000000")
            hex_val_lbl.setTextFormat(Qt.TextFormat.PlainText)
            hex_val_lbl.setStyleSheet("font-size: 8px;")

            chip_lay.addWidget(t_name_lbl)
            chip_lay.addStretch(1)
            chip_lay.addWidget(hex_val_lbl)

            self.matrix_grid.addWidget(chip_frame, row, col)
            self.matrix_chips[token_name] = (chip_frame, t_name_lbl, hex_val_lbl)

        mat_lay.addLayout(self.matrix_grid)
        self.preview_stack.addWidget(page_matrix)

        self.main_layout.addWidget(self.preview_stack)

    def _set_preview_view(self, key: str) -> None:
        idx = {"overview": 0, "table": 1, "matrix": 2}.get(key, 0)
        self.preview_stack.setCurrentIndex(idx)
        if hasattr(self, "_palette") and self._palette:
            self._update_active_view()

    def update_palette(
        self, palette: dict[str, str], primary_hex: str, mode: str, mood: str = "cohesive"
    ) -> None:
        """Apply generated colors to simulated mockup widgets."""
        self._palette = palette
        self._primary_color = primary_hex
        self._mode = mode
        self._mood = mood
        p = palette
        is_dark = mode.lower() != "light"

        # Frame background & border
        self.setStyleSheet(
            f"LiveThemePreviewCard {{ background-color: {p['window']}; "
            f"border: 1px solid {p['border']}; border-radius: 8px; }}"
        )
        self.preview_title.setStyleSheet(f"color: {p['text']}; font-size: 11px; font-weight: 700;")

        # Mode Badge
        mode_label = (
            f"OLED ({mood.upper()})"
            if mood == "oled" and is_dark
            else f"{mode.upper()} ({mood.upper()})"
        )
        self.mode_badge.setText(mode_label)
        self.mode_badge.setStyleSheet(
            f"background-color: {p['accent_soft']}; color: {p['accent']}; "
            f"font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 4px;"
        )

        # Contrast Ratio Rating
        cr = contrast_ratio(p["text"], p["window"])
        if cr >= 7.0:
            cr_text = f"CONTRAST: {cr:.2f} (AAA)"
            cr_bg = p["success_soft"]
            cr_fg = p["success"]
        elif cr >= 4.5:
            cr_text = f"CONTRAST: {cr:.2f} (AA)"
            cr_bg = p["warning_soft"]
            cr_fg = p["warning"]
        else:
            cr_text = f"CONTRAST: {cr:.2f} (LOW)"
            cr_bg = p["danger_soft"]
            cr_fg = p["danger"]

        self.cr_badge.setText(cr_text)
        self.cr_badge.setStyleSheet(
            f"background-color: {cr_bg}; color: {cr_fg}; "
            f"font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 4px;"
        )

        self._update_active_view()

    def _update_active_view(self) -> None:
        if not hasattr(self, "_palette") or not self._palette:
            return
        p = self._palette
        is_dark = getattr(self, "_mode", "dark").lower() != "light"
        idx = self.preview_stack.currentIndex()

        if idx == 0:
            # Overview Tab: update only visible overview elements
            self.stat_box.setStyleSheet(
                f"background-color: {p['surface']}; border: 1px solid {p['border2']}; border-radius: 6px;"
            )
            self.stat_title.setStyleSheet(
                f"color: {p['muted']}; font-size: 9px; font-weight: 700; letter-spacing: 0.5px;"
            )
            self.stat_val.setStyleSheet(f"color: {p['text']}; font-size: 14px; font-weight: 800;")
            self.stat_sub.setStyleSheet(f"color: {p['faint']}; font-size: 10px;")

            self.badges_box.setStyleSheet(
                f"background-color: {p['surface']}; border: 1px solid {p['border2']}; border-radius: 6px;"
            )
            self.badge_safe.setStyleSheet(
                f"background-color: {p['success_soft']}; color: {p['success']}; "
                f"font-size: 8px; font-weight: 700; padding: 2px 5px; border-radius: 4px;"
            )
            self.badge_warn.setStyleSheet(
                f"background-color: {p['warning_soft']}; color: {p['warning']}; "
                f"font-size: 8px; font-weight: 700; padding: 2px 5px; border-radius: 4px;"
            )
            self.badge_danger.setStyleSheet(
                f"background-color: {p['danger_soft']}; color: {p['danger']}; "
                f"font-size: 8px; font-weight: 700; padding: 2px 5px; border-radius: 4px;"
            )

            self.mock_primary_btn.setStyleSheet(
                f"QPushButton {{ background-color: {p['accent']}; color: #ffffff; "
                f"font-weight: 700; border: none; border-radius: 5px; padding: 3px 10px; font-size: 10px; }} "
                f"QPushButton:hover {{ background-color: {p['accent_hover']}; }}"
            )
            self.mock_secondary_btn.setStyleSheet(
                f"QPushButton {{ background-color: {p['surface2']}; color: {p['text']}; "
                f"font-weight: 600; border: 1px solid {p['border']}; border-radius: 5px; padding: 3px 10px; font-size: 10px; }}"
            )
            self.mock_danger_btn.setStyleSheet(
                f"QPushButton {{ background-color: {p['danger_soft']}; color: {p['danger']}; "
                f"font-weight: 600; border: 1px solid {p['danger']}; border-radius: 5px; padding: 3px 10px; font-size: 10px; }}"
            )

            self.swatch_container.setStyleSheet(
                f"background-color: {p['surface2']}; border: 1px solid {p['border']}; border-radius: 6px;"
            )
            for key, pill in self.swatch_labels:
                col = p.get(key, "#888888")
                fg = "#ffffff" if is_dark or key in ("accent", "danger", "success") else "#111827"
                pill.setStyleSheet(
                    f"background-color: {col}; color: {fg}; "
                    f"border: 1px solid {p['border2']}; border-radius: 3px; font-size: 8px; font-weight: 700;"
                )

        elif idx == 1:
            # Table Tab
            self.mock_table.setStyleSheet(
                f"QTableWidget {{ background-color: {p['surface']}; color: {p['text']}; "
                f"gridline-color: {p['border2']}; border: 1px solid {p['border']}; border-radius: 4px; font-size: 10px; }} "
                f"QHeaderView::section {{ background-color: {p['surface2']}; color: {p['muted']}; "
                f"font-weight: 700; border: 1px solid {p['border']}; padding: 2px 4px; }}"
            )

        elif idx == 2:
            # Matrix Tab: 27 token chips
            for token_name, (chip, t_name, hex_val) in self.matrix_chips.items():
                val = p.get(token_name, "#888888")
                chip_fg = ensure_contrast("#ffffff", val, min_ratio=4.0)
                chip.setStyleSheet(
                    f"background-color: {val}; border: 1px solid {p['border2']}; border-radius: 4px;"
                )
                t_name.setStyleSheet(f"color: {chip_fg}; font-size: 8px; font-weight: 700;")
                hex_val.setText(val)
                hex_val.setStyleSheet(f"color: {chip_fg}; font-size: 8px;")


class CustomThemeBuilderWidget(QWidget):
    """Complete Custom Theme Studio component with color picker, presets, mood modes,

    magic generator dice, tuning sliders, live interactive preview, and save/apply actions.
    """

    theme_applied = Signal(dict)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._current_primary = "#3b82f6"
        self._current_mode = "dark"
        self._current_mood = "cohesive"
        self._current_contrast = 1.0
        self._current_intensity = 1.0
        self._current_bg_darkness = 1.0
        self._preset_buttons: list[QPushButton] = []
        self._mood_buttons: dict[str, QPushButton] = {}
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(220)
        self._debounce_timer.timeout.connect(self._apply_debounced)
        self._load_saved_config()
        self._build_ui()
        self._update_preview(auto_apply=False)

    def _load_saved_config(self) -> None:
        try:
            from crapcleaner.config import load_settings

            settings = load_settings()
            cfg = settings.get("custom_theme", {})
            self._current_primary = normalize_hex(cfg.get("primary_color", "#3b82f6"))
            self._current_mode = cfg.get("mode", "dark")
            self._current_mood = cfg.get("mood", "cohesive")
            self._current_contrast = float(cfg.get("surface_contrast", 1.0))
            self._current_intensity = float(cfg.get("accent_intensity", 1.0))
            self._current_bg_darkness = float(cfg.get("bg_darkness", 1.0))
        except Exception:
            pass

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        main_card = QFrame()
        main_card.setProperty("card", "true")
        card_lay = QVBoxLayout(main_card)
        card_lay.setContentsMargins(16, 14, 16, 14)
        card_lay.setSpacing(12)

        # 1. Header Toolbar (Title + Magic Dice + JSON Export/Import)
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("Custom Theme Studio")
        title_lbl.setTextFormat(Qt.TextFormat.PlainText)
        title_lbl_font = title_lbl.font()
        title_lbl_font.setBold(True)
        title_lbl_font.setPointSize(13)
        title_lbl.setFont(title_lbl_font)

        sub_lbl = QLabel(
            "Design your personal CrapCleaner theme with perceptual color math, harmony moods & live previews."
        )
        sub_lbl.setTextFormat(Qt.TextFormat.PlainText)
        sub_lbl.setStyleSheet("font-size: 11px; color: #888888;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        header_row.addLayout(title_box, 1)

        # Quick Action Tools
        self.magic_dice_btn = QPushButton("Surprise Me (Magic Dice)")
        self.magic_dice_btn.setIcon(material_icon("dice", "#ffffff"))
        self.magic_dice_btn.setFixedHeight(30)
        self.magic_dice_btn.setToolTip("Roll a harmonious, professionally balanced palette")
        self.magic_dice_btn.clicked.connect(self._on_magic_dice_clicked)
        header_row.addWidget(self.magic_dice_btn)

        self.copy_json_btn = QPushButton("Copy JSON")
        self.copy_json_btn.setIcon(material_icon("code", "#888888"))
        self.copy_json_btn.setFixedHeight(30)
        self.copy_json_btn.setToolTip("Copy custom theme palette configuration to clipboard")
        self.copy_json_btn.clicked.connect(self._copy_theme_json)
        header_row.addWidget(self.copy_json_btn)

        self.import_json_btn = QPushButton("Import...")
        self.import_json_btn.setIcon(material_icon("download", "#888888"))
        self.import_json_btn.setFixedHeight(30)
        self.import_json_btn.setToolTip("Import custom theme palette from JSON")
        self.import_json_btn.clicked.connect(self._import_theme_json)
        header_row.addWidget(self.import_json_btn)

        card_lay.addLayout(header_row)

        # 2. Main 2-Column Studio Layout
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(16)

        # --- LEFT COLUMN: Studio Controls ---
        left_box = QVBoxLayout()
        left_box.setSpacing(10)

        # A. Primary Color Picker & Hex Input
        color_pick_row = QHBoxLayout()
        color_pick_row.setSpacing(8)

        self.color_swatch_btn = QPushButton()
        self.color_swatch_btn.setFixedSize(36, 36)
        self.color_swatch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.color_swatch_btn.setToolTip("Click to open system color picker")
        self.color_swatch_btn.clicked.connect(self._open_color_dialog)
        color_pick_row.addWidget(self.color_swatch_btn)

        hex_box = QVBoxLayout()
        hex_box.setSpacing(2)
        hex_lbl = QLabel("Primary Accent Color")
        hex_lbl.setTextFormat(Qt.TextFormat.PlainText)
        hex_lbl.setStyleSheet("font-size: 11px; font-weight: 600;")
        self.hex_input = QLineEdit(self._current_primary)
        self.hex_input.setMaxLength(7)
        self.hex_input.setPlaceholderText("#3b82f6")
        self.hex_input.setFixedHeight(28)
        self.hex_input.textChanged.connect(self._on_hex_text_changed)
        hex_box.addWidget(hex_lbl)
        hex_box.addWidget(self.hex_input)
        color_pick_row.addLayout(hex_box, 1)

        left_box.addLayout(color_pick_row)

        # B. Palette Mood / Harmony Style Chips
        mood_lbl = QLabel("Palette Mood & Harmony")
        mood_lbl.setTextFormat(Qt.TextFormat.PlainText)
        mood_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #888888;")
        left_box.addWidget(mood_lbl)

        mood_row = QHBoxLayout()
        mood_row.setSpacing(4)
        self.mood_group = QButtonGroup(self)
        self.mood_group.setExclusive(True)

        mood_labels = [
            ("cohesive", "Cohesive"),
            ("vibrant", "Vibrant"),
            ("muted", "Muted"),
            ("oled", "OLED Pure"),
            ("pastel", "Pastel"),
            ("minimal", "Minimal"),
        ]
        for m_key, m_title in mood_labels:
            btn = QPushButton(m_title)
            btn.setCheckable(True)
            btn.setProperty("chip", "true")
            btn.setFixedHeight(26)
            btn.setChecked(self._current_mood == m_key)
            btn.clicked.connect(lambda _, k=m_key: self._set_mood(k))
            self.mood_group.addButton(btn)
            self._mood_buttons[m_key] = btn
            mood_row.addWidget(btn)

        left_box.addLayout(mood_row)

        # C. 15 Curated Preset Swatches
        presets_lbl = QLabel("Quick Presets (15 Designer Hues)")
        presets_lbl.setTextFormat(Qt.TextFormat.PlainText)
        presets_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #888888;")
        left_box.addWidget(presets_lbl)

        presets_grid = QGridLayout()
        presets_grid.setSpacing(6)
        for idx, (p_name, p_hex) in enumerate(PRESET_COLORS):
            row, col = divmod(idx, 5)
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(f"{p_name} ({p_hex})")
            btn.setStyleSheet(
                f"background-color: {p_hex}; border: 1px solid rgba(255, 255, 255, 0.2); "
                f"border-radius: 12px;"
            )
            btn.clicked.connect(lambda _, h=p_hex: self._set_primary_color(h))
            presets_grid.addWidget(btn, row, col)
            self._preset_buttons.append(btn)
        left_box.addLayout(presets_grid)

        # D. Dark / Light Canvas Mode Toggle
        mode_lbl = QLabel("Canvas Mode")
        mode_lbl.setTextFormat(Qt.TextFormat.PlainText)
        mode_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #888888;")
        left_box.addWidget(mode_lbl)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)

        self.dark_btn = QPushButton("Dark Canvas")
        self.dark_btn.setCheckable(True)
        self.dark_btn.setIcon(material_icon("dark_mode", "#ffffff"))
        self.dark_btn.setIconSize(QSize(14, 14))
        self.dark_btn.setChecked(self._current_mode == "dark")
        self.dark_btn.clicked.connect(lambda: self._set_mode("dark"))
        self.mode_group.addButton(self.dark_btn)
        mode_row.addWidget(self.dark_btn)

        self.light_btn = QPushButton("Light Canvas")
        self.light_btn.setCheckable(True)
        self.light_btn.setIcon(material_icon("light_mode", "#ffffff"))
        self.light_btn.setIconSize(QSize(14, 14))
        self.light_btn.setChecked(self._current_mode == "light")
        self.light_btn.clicked.connect(lambda: self._set_mode("light"))
        self.mode_group.addButton(self.light_btn)
        mode_row.addWidget(self.light_btn)

        left_box.addLayout(mode_row)

        # E. Sliders for Surface Contrast & Accent Intensity
        sliders_box = QVBoxLayout()
        sliders_box.setSpacing(6)

        # Contrast Slider
        c_label_row = QHBoxLayout()
        self.contrast_title = QLabel("Surface Contrast")
        self.contrast_title.setTextFormat(Qt.TextFormat.PlainText)
        self.contrast_title.setStyleSheet("font-size: 11px; color: #888888;")
        self.contrast_val_lbl = QLabel(f"{int(self._current_contrast * 100)}%")
        self.contrast_val_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self.contrast_val_lbl.setStyleSheet("font-size: 11px; font-weight: 700;")
        c_label_row.addWidget(self.contrast_title)
        c_label_row.addStretch(1)
        c_label_row.addWidget(self.contrast_val_lbl)
        sliders_box.addLayout(c_label_row)

        self.contrast_slider = QSlider(Qt.Orientation.Horizontal)
        self.contrast_slider.setRange(60, 140)
        self.contrast_slider.setValue(int(self._current_contrast * 100))
        self.contrast_slider.valueChanged.connect(self._on_contrast_changed)
        self.contrast_slider.sliderReleased.connect(self._apply_debounced)
        sliders_box.addWidget(self.contrast_slider)

        # Accent Intensity Slider
        a_label_row = QHBoxLayout()
        self.intensity_title = QLabel("Accent Vibrancy")
        self.intensity_title.setTextFormat(Qt.TextFormat.PlainText)
        self.intensity_title.setStyleSheet("font-size: 11px; color: #888888;")
        self.intensity_val_lbl = QLabel(f"{int(self._current_intensity * 100)}%")
        self.intensity_val_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self.intensity_val_lbl.setStyleSheet("font-size: 11px; font-weight: 700;")
        a_label_row.addWidget(self.intensity_title)
        a_label_row.addStretch(1)
        a_label_row.addWidget(self.intensity_val_lbl)
        sliders_box.addLayout(a_label_row)

        self.intensity_slider = QSlider(Qt.Orientation.Horizontal)
        self.intensity_slider.setRange(50, 150)
        self.intensity_slider.setValue(int(self._current_intensity * 100))
        self.intensity_slider.valueChanged.connect(self._on_intensity_changed)
        self.intensity_slider.sliderReleased.connect(self._apply_debounced)
        sliders_box.addWidget(self.intensity_slider)

        left_box.addLayout(sliders_box)
        columns_layout.addLayout(left_box, 1)

        # --- RIGHT COLUMN: Live Preview ---
        self.preview_card = LiveThemePreviewCard(main_card)
        columns_layout.addWidget(self.preview_card, 1)

        card_lay.addLayout(columns_layout)

        # 3. Bottom Action Bar
        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        self.reset_btn = QPushButton("Reset Defaults")
        self.reset_btn.setIcon(material_icon("refresh", "#888888"))
        self.reset_btn.clicked.connect(self._reset_to_defaults)
        actions_row.addWidget(self.reset_btn)

        actions_row.addStretch(1)

        self.apply_btn = QPushButton("Apply && Save Custom Theme")
        self.apply_btn.setProperty("primary", "true")
        self.apply_btn.setIcon(material_icon("check", "#ffffff"))
        self.apply_btn.setFixedHeight(34)
        self.apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_btn.clicked.connect(self._apply_and_save)
        actions_row.addWidget(self.apply_btn)

        card_lay.addLayout(actions_row)
        root.addWidget(main_card)

    # -----------------------------------------------------------------------
    # Event Handlers & State Management
    # -----------------------------------------------------------------------

    def _open_color_dialog(self) -> None:
        init_col = QColor(self._current_primary)
        col = QColorDialog.getColor(
            init_col,
            self.window(),
            "Select Primary Theme Color",
        )
        if col.isValid():
            self._set_primary_color(col.name())

    def _on_hex_text_changed(self, text: str) -> None:
        clean = text.strip()
        if not clean.startswith("#"):
            clean = f"#{clean}"
        if len(clean) == 7 and normalize_hex(clean) == clean.lower():
            self._current_primary = clean.lower()
            self._update_preview(auto_apply=True)

    def _set_primary_color(self, hex_code: str) -> None:
        normalized = normalize_hex(hex_code)
        self._current_primary = normalized
        self.hex_input.blockSignals(True)
        self.hex_input.setText(normalized)
        self.hex_input.blockSignals(False)
        self._update_preview(auto_apply=True)

    def _set_mode(self, mode: str) -> None:
        self._current_mode = mode
        self._update_preview(auto_apply=True)

    def _set_mood(self, mood: str) -> None:
        self._current_mood = mood
        self._update_preview(auto_apply=True)

    def _on_contrast_changed(self, value: int) -> None:
        self._current_contrast = value / 100.0
        self.contrast_val_lbl.setText(f"{value}%")
        self._update_preview(auto_apply=False, full_restyle=False)
        self._debounce_timer.start(220)

    def _on_intensity_changed(self, value: int) -> None:
        self._current_intensity = value / 100.0
        self.intensity_val_lbl.setText(f"{value}%")
        self._update_preview(auto_apply=False, full_restyle=False)
        self._debounce_timer.start(220)

    def _apply_debounced(self) -> None:
        self._debounce_timer.stop()
        self._update_preview(auto_apply=True, full_restyle=True)

    def _on_magic_dice_clicked(self) -> None:
        """Roll random beautiful theme configuration."""
        magic = generate_magic_palette()
        self._current_primary = magic["primary_color"]
        self._current_mode = magic["mode"]
        self._current_mood = magic["mood"]
        self._current_contrast = magic["surface_contrast"]
        self._current_intensity = magic["accent_intensity"]

        self.hex_input.blockSignals(True)
        self.hex_input.setText(self._current_primary)
        self.hex_input.blockSignals(False)

        self.dark_btn.setChecked(self._current_mode == "dark")
        self.light_btn.setChecked(self._current_mode == "light")

        if self._current_mood in self._mood_buttons:
            self._mood_buttons[self._current_mood].setChecked(True)

        self.contrast_slider.setValue(int(self._current_contrast * 100))
        self.intensity_slider.setValue(int(self._current_intensity * 100))
        self._update_preview(auto_apply=True)

    def _copy_theme_json(self) -> None:
        cfg = {
            "primary_color": self._current_primary,
            "mode": self._current_mode,
            "mood": self._current_mood,
            "surface_contrast": self._current_contrast,
            "accent_intensity": self._current_intensity,
            "bg_darkness": self._current_bg_darkness,
        }
        json_str = export_custom_theme_json(cfg)
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(json_str)
            QMessageBox.information(
                self, "Theme Copied", "Custom theme configuration copied to clipboard."
            )

    def _import_theme_json(self) -> None:
        text, ok = QInputDialog.getMultiLineText(
            self,
            "Import Custom Theme JSON",
            "Paste theme JSON configuration below:",
            "",
        )
        if ok and text.strip():
            imported = import_custom_theme_json(text.strip())
            if imported:
                self._current_primary = imported["primary_color"]
                self._current_mode = imported["mode"]
                self._current_mood = imported["mood"]
                self._current_contrast = imported["surface_contrast"]
                self._current_intensity = imported["accent_intensity"]
                self._current_bg_darkness = imported["bg_darkness"]

                self.hex_input.setText(self._current_primary)
                self.dark_btn.setChecked(self._current_mode == "dark")
                self.light_btn.setChecked(self._current_mode == "light")
                if self._current_mood in self._mood_buttons:
                    self._mood_buttons[self._current_mood].setChecked(True)
                self.contrast_slider.setValue(int(self._current_contrast * 100))
                self.intensity_slider.setValue(int(self._current_intensity * 100))
                self._update_preview(auto_apply=True)
            else:
                QMessageBox.warning(self, "Import Error", "Invalid theme JSON configuration.")

    def _update_preview(self, auto_apply: bool = False, full_restyle: bool = True) -> None:
        palette = generate_custom_palette(
            primary_color=self._current_primary,
            mode=self._current_mode,
            surface_contrast=self._current_contrast,
            accent_intensity=self._current_intensity,
            bg_darkness=self._current_bg_darkness,
            mood=self._current_mood,
        )
        self.preview_card.update_palette(
            palette, self._current_primary, self._current_mode, self._current_mood
        )

        if full_restyle or auto_apply:
            self.color_swatch_btn.setStyleSheet(
                f"background-color: {self._current_primary}; border: 2px solid #ffffff; "
                f"border-radius: 18px;"
            )
            # Style Dark / Light mode segment buttons cleanly
            is_dark = self._current_mode == "dark"
            active_btn_style = (
                f"QPushButton {{ background-color: {palette['accent']}; color: #ffffff; "
                f"border: 1px solid {palette['accent_hover']}; border-radius: 6px; padding: 6px 12px; font-weight: 700; font-size: 11px; }}"
            )
            inactive_btn_style = (
                f"QPushButton {{ background-color: {palette['surface2']}; color: {palette['muted']}; "
                f"border: 1px solid {palette['border']}; border-radius: 6px; padding: 6px 12px; font-weight: 500; font-size: 11px; }}"
                f"QPushButton:hover {{ background-color: {palette['elevated']}; color: {palette['text']}; }}"
            )
            self.dark_btn.setStyleSheet(active_btn_style if is_dark else inactive_btn_style)
            self.light_btn.setStyleSheet(inactive_btn_style if is_dark else active_btn_style)
            self.dark_btn.setIcon(
                material_icon("dark_mode", "#ffffff" if is_dark else palette["muted"])
            )
            self.light_btn.setIcon(
                material_icon("light_mode", palette["muted"] if is_dark else "#ffffff")
            )

        if auto_apply:
            custom_cfg = {
                "primary_color": self._current_primary,
                "mode": self._current_mode,
                "mood": self._current_mood,
                "surface_contrast": self._current_contrast,
                "accent_intensity": self._current_intensity,
                "bg_darkness": self._current_bg_darkness,
            }
            self.theme_applied.emit(custom_cfg)

    def _apply_and_save(self) -> None:
        custom_cfg = {
            "primary_color": self._current_primary,
            "mode": self._current_mode,
            "mood": self._current_mood,
            "surface_contrast": self._current_contrast,
            "accent_intensity": self._current_intensity,
            "bg_darkness": self._current_bg_darkness,
        }
        self.theme_applied.emit(custom_cfg)

    def _reset_to_defaults(self) -> None:
        self._current_primary = "#3b82f6"
        self._current_mode = "dark"
        self._current_mood = "cohesive"
        self._current_contrast = 1.0
        self._current_intensity = 1.0
        self._current_bg_darkness = 1.0
        self.hex_input.setText("#3b82f6")
        self.dark_btn.setChecked(True)
        if "cohesive" in self._mood_buttons:
            self._mood_buttons["cohesive"].setChecked(True)
        self.contrast_slider.setValue(100)
        self.intensity_slider.setValue(100)
        self._update_preview(auto_apply=True)
