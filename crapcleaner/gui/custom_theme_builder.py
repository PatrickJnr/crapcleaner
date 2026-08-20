"""Custom Theme Studio & Builder Widget for CrapCleaner GUI.

Pick a primary colour and a mood style, choose a dark or light canvas, tune
contrast and vibrancy, and see the result on a live mockup before saving.
"""

from __future__ import annotations

import itertools

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.gui.color_engine import (
    contrast_ratio,
    ensure_contrast,
    flatten_alpha,
    generate_custom_palette,
    generate_magic_palette,
    normalize_hex,
)
from crapcleaner.gui.icons import icon as material_icon

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


#: The colour pairs the running application actually draws, and what each one is.
CONTRAST_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("text", "window", "Body text on the window"),
    ("text", "surface", "Body text on a card"),
    ("text", "elevated", "Body text on a raised panel"),
    ("muted", "window", "Secondary text on the window"),
    ("muted", "surface", "Secondary text on a card"),
    ("muted", "elevated", "Secondary text on a raised panel"),
    ("on_accent_soft", "accent_soft", "Accent badge label"),
    ("on_success_soft", "success_soft", "Safe badge label"),
    ("on_warning_soft", "warning_soft", "Warning badge label"),
    ("on_danger_soft", "danger_soft", "Critical badge label"),
    ("on_accent", "accent", "Primary button label"),
    ("on_danger", "danger", "Danger button label"),
)

#: WCAG 2.1 AA for body text.
MIN_PAIR_CONTRAST = 4.5


def contrast_report(palette: dict[str, str]) -> list[tuple[str, float, str]]:
    """Every pair the running application draws, as it actually renders.

    Soft badge tints are translucent and so are composited over the card first:
    measuring the raw ``rgba()`` against its own accent reports about 1:1 for
    every theme, which says nothing.
    """
    if not palette:
        return []
    card = palette.get("surface", "#202020")
    rows = []
    for fg_key, bg_key, pair_label in CONTRAST_PAIRS:
        foreground = palette.get(fg_key, "#888888")
        background = flatten_alpha(palette.get(bg_key, "#888888"), card)
        ratio = contrast_ratio(foreground, background)
        grade = "AAA" if ratio >= 7.0 else "AA" if ratio >= MIN_PAIR_CONTRAST else "FAILS"
        rows.append((pair_label, ratio, grade))
    return rows


def _failing_pairs(config: dict) -> int:
    palette = generate_custom_palette(
        primary_color=config["primary_color"],
        mode=config["mode"],
        mood=config["mood"],
        surface_contrast=config["surface_contrast"],
        accent_intensity=config["accent_intensity"],
        bg_darkness=config["bg_darkness"],
    )
    return sum(1 for _, _, grade in contrast_report(palette) if grade == "FAILS")


_SLIDERS: tuple[tuple[str, str, float, float], ...] = (
    ("surface_contrast", "Surface Contrast", 0.60, 1.40),
    ("accent_intensity", "Accent Vibrancy", 0.50, 1.50),
    ("bg_darkness", "Background Depth", 0.50, 1.50),
)


def _sweep(config: dict, grids: list[list[float]]) -> tuple[dict, float] | None:
    """The combination clearing every pair that moves the sliders least."""
    best: tuple[float, dict] | None = None
    for values in itertools.product(*grids):
        candidate = dict(config)
        moved = 0.0
        for (knob, _label, _low, _high), value in zip(_SLIDERS, values):
            candidate[knob] = value
            moved += abs(value - config[knob])
        if _failing_pairs(candidate) == 0 and (best is None or moved < best[0]):
            best = (moved, candidate)
    return (best[1], best[0]) if best else None


def plan_readability_fix(config: dict) -> tuple[dict, list[str]]:
    """Find settings that read, and say what changed to get there.

    A sweep rather than a walk: the three sliders interact (Surface Contrast
    lightens the panel secondary text sits on), so moving one at a time and
    keeping only moves that help alone walks past combinations that work. The
    result is the passing combination nearest to what was set.
    """
    if _failing_pairs(config) == 0:
        return dict(config), []

    def grid(low: float, high: float, step: float) -> list[float]:
        count = int(round((high - low) / step))
        return [round(low + i * step, 3) for i in range(count + 1)]

    coarse = _sweep(config, [grid(low, high, 0.1) for _knob, _l, low, high in _SLIDERS])
    if coarse is None:
        return dict(config), []

    found, _moved = coarse
    fine = _sweep(
        config,
        [
            grid(
                max(low, found[knob] - 0.1),
                min(high, found[knob] + 0.1),
                0.025,
            )
            for knob, _label, low, high in _SLIDERS
        ],
    )
    if fine is not None:
        found = fine[0]

    notes = [
        f"set {label} to {int(round(found[knob] * 100))}%"
        for knob, label, _low, _high in _SLIDERS
        if abs(found[knob] - config[knob]) > 0.005
    ]
    return found, notes


class LiveThemePreviewCard(QFrame):
    """A miniature of the application, plus every token the palette defines."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._palette: dict[str, str] = {}
        self._primary_color: str = "#3b82f6"
        self._mode: str = "dark"
        self._mood: str = "cohesive"
        self._build_ui()

    def _build_ui(self) -> None:
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 12, 14, 12)
        self.main_layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        self.preview_title = QLabel("Live Theme Preview")
        self.preview_title.setObjectName("previewTitle")
        self.preview_title.setTextFormat(Qt.TextFormat.PlainText)
        t_font = self.preview_title.font()
        t_font.setBold(True)
        t_font.setPointSize(11)
        self.preview_title.setFont(t_font)
        header_row.addWidget(self.preview_title)

        self.mode_badge = QLabel("DARK MODE")
        self.mode_badge.setObjectName("modeBadge")
        self.mode_badge.setTextFormat(Qt.TextFormat.PlainText)
        self.mode_badge.setStyleSheet(
            "font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 4px;"
        )
        header_row.addWidget(self.mode_badge)

        self.cr_badge = QLabel("CONTRAST: AAA")
        self.cr_badge.setObjectName("crBadge")
        self.cr_badge.setTextFormat(Qt.TextFormat.PlainText)
        self.cr_badge.setStyleSheet(
            "font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 4px;"
        )
        header_row.addWidget(self.cr_badge)

        header_row.addStretch(1)

        self.main_layout.addLayout(header_row)

        # Everything at once: the three tabs this replaced hid two thirds of the
        # palette behind a click.
        self.mini_window = QFrame()
        self.mini_window.setObjectName("miniWindow")
        mini_lay = QHBoxLayout(self.mini_window)
        mini_lay.setContentsMargins(1, 1, 1, 1)
        mini_lay.setSpacing(0)

        self.mini_nav = QFrame()
        self.mini_nav.setObjectName("miniNav")
        self.mini_nav.setFixedWidth(132)
        nav_lay = QVBoxLayout(self.mini_nav)
        nav_lay.setContentsMargins(8, 10, 8, 10)
        nav_lay.setSpacing(2)

        self.mini_brand = QLabel("CrapCleaner")
        self.mini_brand.setObjectName("miniBrand")
        self.mini_brand.setTextFormat(Qt.TextFormat.PlainText)
        nav_lay.addWidget(self.mini_brand)
        nav_lay.addSpacing(8)

        self.mini_nav_items: list[tuple[QLabel, bool]] = []
        for name, active in (
            ("Dashboard", False),
            ("Cleanup", False),
            ("Storage Breakdown", True),
            ("Large Files", False),
            ("Duplicates", False),
            ("Startup Apps", False),
            ("Services", False),
            ("History", False),
        ):
            item = QLabel(name)
            item.setObjectName("navItemActive" if active else "navItem")
            item.setTextFormat(Qt.TextFormat.PlainText)
            item.setFixedHeight(22)
            nav_lay.addWidget(item)
            self.mini_nav_items.append((item, active))
        nav_lay.addStretch(1)

        self.mini_nav_footer = QLabel("Scans never delete files.")
        self.mini_nav_footer.setObjectName("miniNavFooter")
        self.mini_nav_footer.setTextFormat(Qt.TextFormat.PlainText)
        self.mini_nav_footer.setWordWrap(True)
        nav_lay.addWidget(self.mini_nav_footer)
        mini_lay.addWidget(self.mini_nav)

        content = QWidget()
        content_lay = QVBoxLayout(content)
        content_lay.setContentsMargins(12, 10, 12, 10)
        content_lay.setSpacing(8)

        head_row = QHBoxLayout()
        head_box = QVBoxLayout()
        head_box.setSpacing(1)
        self.mini_heading = QLabel("Storage Breakdown")
        self.mini_heading.setObjectName("miniHeading")
        self.mini_heading.setTextFormat(Qt.TextFormat.PlainText)
        self.mini_subheading = QLabel("What is using the disk, and what is safe to remove.")
        self.mini_subheading.setObjectName("miniSubheading")
        self.mini_subheading.setTextFormat(Qt.TextFormat.PlainText)
        head_box.addWidget(self.mini_heading)
        head_box.addWidget(self.mini_subheading)
        head_row.addLayout(head_box, 1)

        self.mock_primary_btn = QPushButton("Clean Junk")
        self.mock_primary_btn.setObjectName("mockPrimary")
        self.mock_primary_btn.setFixedHeight(26)
        self.mock_primary_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        head_row.addWidget(self.mock_primary_btn)
        content_lay.addLayout(head_row)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        self.mini_stats: list[tuple[QFrame, QLabel, QLabel]] = []
        for caption, value in (
            ("RECLAIMABLE", "6.42 GB"),
            ("ITEMS FOUND", "5,280"),
            ("DISK IN USE", "78%"),
        ):
            box = QFrame()
            box.setObjectName("statBox")
            box.setFixedHeight(52)
            box_lay = QVBoxLayout(box)
            box_lay.setContentsMargins(10, 6, 10, 6)
            box_lay.setSpacing(1)
            cap = QLabel(caption)
            cap.setObjectName("statCaption")
            cap.setTextFormat(Qt.TextFormat.PlainText)
            figure = QLabel(value)
            figure.setObjectName("statFigure")
            figure.setTextFormat(Qt.TextFormat.PlainText)
            box_lay.addWidget(cap)
            box_lay.addWidget(figure)
            stats_row.addWidget(box, 1)
            self.mini_stats.append((box, cap, figure))
        content_lay.addLayout(stats_row)

        self.mini_list = QTableWidget(0, 3)
        self.mini_list.setObjectName("miniList")
        self.mini_list.setAccessibleName("Palette preview rows")
        self.mini_list.setHorizontalHeaderLabels(["Location", "Size", "Risk"])
        self.mini_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.mini_list.verticalHeader().setVisible(False)
        self.mini_list.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.mini_list.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.mini_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.mini_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        mini_rows = [
            ("Windows Update cache", "2.30 GB", "Safe"),
            ("Crash dumps", "1.96 GB", "Review"),
            ("Package manager caches", "1.14 GB", "Safe"),
            ("Browser caches", "812 MB", "Safe"),
            ("Old installers", "620 MB", "Review"),
            ("Delivery Optimisation", "486 MB", "Safe"),
            ("Windows error reports", "310 MB", "Safe"),
            ("Thumbnail database", "184 MB", "Safe"),
            ("Font cache", "96 MB", "Safe"),
            ("Temporary internet files", "74 MB", "Safe"),
            ("Recycle Bin", "62 MB", "Review"),
            ("Log files", "48 MB", "Safe"),
            ("Prefetch data", "31 MB", "Safe"),
            ("Memory dumps", "18 MB", "Review"),
            ("Clipboard history", "12 MB", "Safe"),
            ("Search index fragments", "9 MB", "Safe"),
        ]
        self.mini_list.setRowCount(len(mini_rows))
        for r, mini_row in enumerate(mini_rows):
            for c, text in enumerate(mini_row):
                cell = QTableWidgetItem(text)
                if c:
                    cell.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.mini_list.setItem(r, c, cell)
        content_lay.addWidget(self.mini_list, 1)

        foot_row = QHBoxLayout()
        foot_row.setSpacing(6)
        self.badge_safe = QLabel("SAFE")
        self.badge_warn = QLabel("REVIEW")
        self.badge_danger = QLabel("CRITICAL")
        for badge, role in (
            (self.badge_safe, "success"),
            (self.badge_warn, "warning"),
            (self.badge_danger, "danger"),
        ):
            badge.setObjectName(f"badge_{role}")
            badge.setTextFormat(Qt.TextFormat.PlainText)
            badge.setFixedHeight(18)
            foot_row.addWidget(badge)
        foot_row.addStretch(1)

        self.mock_secondary_btn = QPushButton("Deep Scan")
        self.mock_secondary_btn.setObjectName("mockSecondary")
        self.mock_secondary_btn.setFixedHeight(26)
        self.mock_danger_btn = QPushButton("Purge All")
        self.mock_danger_btn.setObjectName("mockDanger")
        self.mock_danger_btn.setFixedHeight(26)
        foot_row.addWidget(self.mock_secondary_btn)
        foot_row.addWidget(self.mock_danger_btn)
        content_lay.addLayout(foot_row)

        mini_lay.addWidget(content, 1)
        self.main_layout.addWidget(self.mini_window, 1)

        tokens_lbl = QLabel("PALETTE")
        tokens_lbl.setObjectName("tokensLabel")
        tokens_lbl.setTextFormat(Qt.TextFormat.PlainText)
        tokens_lbl.setStyleSheet("font-size: 9px; font-weight: 700; letter-spacing: 0.5px;")
        self.tokens_label = tokens_lbl
        self.main_layout.addWidget(tokens_lbl)

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
            "faint",
            "accent",
            "accent_hover",
            "success",
            "warning",
            "danger",
            "info",
            "review",
        ]
        for idx, token_name in enumerate(matrix_tokens):
            grid_row, grid_col = divmod(idx, 4)
            chip_frame = QFrame()
            chip_frame.setObjectName(f"chip_{token_name}")
            chip_frame.setFixedHeight(26)
            chip_lay = QHBoxLayout(chip_frame)
            chip_lay.setContentsMargins(6, 2, 6, 2)
            chip_lay.setSpacing(4)

            t_name_lbl = QLabel(token_name)
            t_name_lbl.setObjectName(f"chipName_{token_name}")
            t_name_lbl.setTextFormat(Qt.TextFormat.PlainText)
            hex_val_lbl = QLabel("#000000")
            hex_val_lbl.setObjectName(f"chipHex_{token_name}")
            hex_val_lbl.setTextFormat(Qt.TextFormat.PlainText)

            chip_lay.addWidget(t_name_lbl)
            chip_lay.addStretch(1)
            chip_lay.addWidget(hex_val_lbl)

            self.matrix_grid.addWidget(chip_frame, grid_row, grid_col)
            self.matrix_chips[token_name] = (chip_frame, t_name_lbl, hex_val_lbl)
        self.main_layout.addLayout(self.matrix_grid)

    def update_palette(
        self, palette: dict[str, str], primary_hex: str, mode: str, mood: str = "cohesive"
    ) -> None:
        """Restyle the preview to a palette, in one pass."""
        if (
            palette == self._palette
            and mode == self._mode
            and mood == self._mood
            and primary_hex == self._primary_color
        ):
            return

        self._palette = palette
        self._primary_color = primary_hex
        self._mode = mode
        self._mood = mood
        p = palette
        is_dark = mode.lower() != "light"

        self.mode_badge.setText(
            f"OLED ({mood.upper()})"
            if mood == "oled" and is_dark
            else f"{mode.upper()} ({mood.upper()})"
        )

        ratio = contrast_ratio(p["text"], p["window"])
        failures = self.contrast_failures()
        if failures:
            cr_text = f"{len(failures)} BELOW {MIN_PAIR_CONTRAST}:1"
            cr_role = "danger"
        elif ratio >= 7.0:
            cr_text = f"CONTRAST: {ratio:.2f} (AAA)"
            cr_role = "success"
        else:
            cr_text = f"CONTRAST: {ratio:.2f} (AA)"
            cr_role = "warning"
        self.cr_badge.setText(cr_text)
        self.cr_badge.setToolTip(
            "Every colour pair the interface draws is checked against WCAG AA. "
            "The report beside the controls has the detail."
        )

        for token_name, (_chip, _name, hex_val) in self.matrix_chips.items():
            hex_val.setText(flatten_alpha(p.get(token_name, "#888888"), p["surface"]))

        self.setStyleSheet(self._stylesheet(p, cr_role))

    def _stylesheet(self, p: dict[str, str], cr_role: str) -> str:
        """The whole preview as one sheet.

        Qt recomputes a widget's style on every `setStyleSheet`, and styling each
        mock widget separately meant ninety-nine of them per edit.
        """
        chip_rules = []
        for token in self.matrix_chips:
            solid = flatten_alpha(p.get(token, "#888888"), p["surface"])
            ink = ensure_contrast("#ffffff", solid, min_ratio=4.0)
            chip_rules.append(
                f"#chip_{token} {{ background-color: {solid}; "
                f"border: 1px solid {p['border2']}; border-radius: 4px; }}"
                f"#chipName_{token} {{ color: {ink}; font-size: 9px; font-weight: 700; }}"
                f"#chipHex_{token} {{ color: {ink}; font-size: 9px; }}"
            )
        chips = "".join(chip_rules)
        badges = "".join(
            f"#badge_{role} {{ background-color: {p[role + '_soft']}; "
            f"color: {p['on_' + role + '_soft']}; font-size: 8px; font-weight: 700; "
            f"padding: 2px 8px; border-radius: 9px; }}"
            for role in ("success", "warning", "danger")
        )
        return f"""
        LiveThemePreviewCard {{
            background-color: {p["window"]};
            border: 1px solid {p["border"]};
            border-radius: 8px;
        }}
        #previewTitle {{ color: {p["text"]}; font-size: 11px; font-weight: 700; }}
        #modeBadge {{
            background-color: {p["accent_soft"]}; color: {p["on_accent_soft"]};
            font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 4px;
        }}
        #crBadge {{
            background-color: {p[cr_role + "_soft"]}; color: {p["on_" + cr_role + "_soft"]};
            font-size: 9px; font-weight: 700; padding: 2px 6px; border-radius: 4px;
        }}
        #miniWindow {{
            background-color: {p["window"]};
            border: 1px solid {p["border"]};
            border-radius: 6px;
        }}
        #miniNav {{
            background-color: {p["panel"]};
            border: none;
            border-right: 1px solid {p["border"]};
        }}
        #miniBrand {{ color: {p["text"]}; font-size: 11px; font-weight: 800; }}
        #navItem {{ color: {p["muted"]}; padding: 2px 6px; font-size: 9px; }}
        #navItemActive {{
            background-color: {p["accent_soft"]}; color: {p["on_accent_soft"]};
            border-left: 2px solid {p["accent"]}; border-radius: 4px;
            padding: 2px 6px; font-size: 9px; font-weight: 700;
        }}
        #miniNavFooter {{ color: {p["faint"]}; font-size: 8px; }}
        #miniHeading {{ color: {p["text"]}; font-size: 13px; font-weight: 800; }}
        #miniSubheading {{ color: {p["muted"]}; font-size: 9px; }}
        #statBox {{
            background-color: {p["surface"]};
            border: 1px solid {p["border2"]};
            border-radius: 6px;
        }}
        #statCaption {{
            color: {p["muted"]}; font-size: 8px; font-weight: 700;
            letter-spacing: 0.5px; border: none;
        }}
        #statFigure {{ color: {p["text"]}; font-size: 15px; font-weight: 800; border: none; }}
        #miniList {{
            background-color: {p["surface"]}; color: {p["text"]};
            gridline-color: {p["border2"]}; border: 1px solid {p["border"]};
            border-radius: 6px; font-size: 10px;
        }}
        #miniList::item {{ padding: 2px 6px; }}
        #miniList QHeaderView::section {{
            background-color: {p["surface2"]}; color: {p["muted"]};
            font-weight: 700; font-size: 9px; border: none;
            border-bottom: 1px solid {p["border"]}; padding: 4px 6px;
        }}
        #mockPrimary {{
            background-color: {p["accent"]}; color: {p["on_accent"]};
            font-weight: 700; border: none; border-radius: 5px;
            padding: 3px 12px; font-size: 10px;
        }}
        #mockPrimary:hover {{ background-color: {p["accent_hover"]}; }}
        #mockSecondary {{
            background-color: {p["surface2"]}; color: {p["text"]};
            font-weight: 600; border: 1px solid {p["border"]}; border-radius: 5px;
            padding: 3px 12px; font-size: 10px;
        }}
        #mockDanger {{
            background-color: {p["danger_soft"]}; color: {p["on_danger_soft"]};
            font-weight: 600; border: 1px solid {p["danger"]}; border-radius: 5px;
            padding: 3px 12px; font-size: 10px;
        }}
        #tokensLabel {{
            color: {p["muted"]}; font-size: 9px; font-weight: 700; letter-spacing: 0.5px;
        }}
        {badges}
        {chips}
        """

    def contrast_failures(self) -> list[tuple[str, float]]:
        """What a reader would struggle with, worst first."""
        return sorted(
            [
                (label, ratio)
                for label, ratio, grade in contrast_report(self._palette)
                if grade == "FAILS"
            ],
            key=lambda item: item[1],
        )


class CustomThemeBuilderWidget(QWidget):
    """The Theme Studio page: controls on the left, live preview on the right."""

    theme_applied = Signal(dict)
    #: A theme was saved to the gallery; carries its id.
    theme_saved = Signal(str)

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
        self._debounce_timer.setInterval(160)
        self._debounce_timer.timeout.connect(self._apply_debounced)
        # A redraw costs about 12ms, so a drag firing one per notch spends longer
        # redrawing than moving: leading edge, then at most one per frame, and always
        # a final one with the value the drag ended on.
        self._preview_pending = False
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(30)
        self._preview_timer.timeout.connect(self._preview_cooldown)
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

        self.magic_dice_btn = QPushButton("Surprise Me (Magic Dice)")
        self.magic_dice_btn.setIcon(material_icon("dice", "#ffffff"))
        self.magic_dice_btn.setFixedHeight(30)
        self.magic_dice_btn.setToolTip("Roll a harmonious, professionally balanced palette")
        self.magic_dice_btn.clicked.connect(self._on_magic_dice_clicked)
        header_row.addWidget(self.magic_dice_btn)

        card_lay.addLayout(header_row)

        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(16)

        left_box = QVBoxLayout()
        left_box.setSpacing(10)

        # Most people want to nudge a theme they already like rather than build one
        # from nothing, which was the only way to use this page.
        start_row = QHBoxLayout()
        start_row.setSpacing(8)
        start_lbl = QLabel("Start from")
        start_lbl.setTextFormat(Qt.TextFormat.PlainText)
        start_lbl.setStyleSheet("font-size: 11px; font-weight: 600;")
        start_row.addWidget(start_lbl)

        self.start_from = QComboBox()
        self.start_from.setFixedHeight(28)
        self.start_from.setAccessibleName("Start from an existing theme")
        self.start_from.setToolTip("Load a theme's colours into the Studio and edit from there.")
        self.start_from.activated.connect(self._on_start_from)
        start_row.addWidget(self.start_from, 1)
        left_box.addLayout(start_row)
        self._populate_start_from()

        self.start_note = QLabel("")
        self.start_note.setTextFormat(Qt.TextFormat.PlainText)
        self.start_note.setWordWrap(True)
        self.start_note.setStyleSheet("font-size: 10px; color: #888888;")
        self.start_note.setVisible(False)
        left_box.addWidget(self.start_note)

        color_pick_row = QHBoxLayout()
        color_pick_row.setSpacing(8)

        self.color_swatch_btn = QPushButton()
        self.color_swatch_btn.setFixedSize(36, 36)
        self.color_swatch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.color_swatch_btn.setToolTip("Click to open system color picker")
        self.color_swatch_btn.setAccessibleName("Pick the primary colour")
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
        self.hex_input.setAccessibleName("Primary colour hex code")
        self.hex_input.setFixedHeight(28)
        self.hex_input.textChanged.connect(self._on_hex_text_changed)
        hex_box.addWidget(hex_lbl)
        hex_box.addWidget(self.hex_input)
        color_pick_row.addLayout(hex_box, 1)

        left_box.addLayout(color_pick_row)

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
            btn.setAccessibleName(f"{m_title} palette mood")
            btn.clicked.connect(lambda _, k=m_key: self._set_mood(k))
            self.mood_group.addButton(btn)
            self._mood_buttons[m_key] = btn
            mood_row.addWidget(btn)

        left_box.addLayout(mood_row)

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
            btn.setAccessibleName(f"Preset colour: {p_name}")
            btn.setStyleSheet(
                f"background-color: {p_hex}; border: 1px solid rgba(255, 255, 255, 0.2); "
                f"border-radius: 12px;"
            )
            btn.clicked.connect(lambda _, h=p_hex: self._set_primary_color(h))
            presets_grid.addWidget(btn, row, col)
            self._preset_buttons.append(btn)
        left_box.addLayout(presets_grid)

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

        sliders_box = QVBoxLayout()
        sliders_box.setSpacing(6)

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
        self.contrast_slider.setAccessibleName("Surface contrast")
        self.contrast_slider.valueChanged.connect(self._on_contrast_changed)
        self.contrast_slider.sliderReleased.connect(self._apply_debounced)
        sliders_box.addWidget(self.contrast_slider)

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
        self.intensity_slider.setAccessibleName("Accent vibrancy")
        self.intensity_slider.valueChanged.connect(self._on_intensity_changed)
        self.intensity_slider.sliderReleased.connect(self._apply_debounced)
        sliders_box.addWidget(self.intensity_slider)

        d_label_row = QHBoxLayout()
        self.darkness_title = QLabel("Background Depth")
        self.darkness_title.setTextFormat(Qt.TextFormat.PlainText)
        self.darkness_title.setStyleSheet("font-size: 11px; color: #888888;")
        self.darkness_val_lbl = QLabel(f"{int(self._current_bg_darkness * 100)}%")
        self.darkness_val_lbl.setTextFormat(Qt.TextFormat.PlainText)
        self.darkness_val_lbl.setStyleSheet("font-size: 11px; font-weight: 700;")
        d_label_row.addWidget(self.darkness_title)
        d_label_row.addStretch(1)
        d_label_row.addWidget(self.darkness_val_lbl)
        sliders_box.addLayout(d_label_row)

        self.darkness_slider = QSlider(Qt.Orientation.Horizontal)
        self.darkness_slider.setRange(50, 150)
        self.darkness_slider.setValue(int(self._current_bg_darkness * 100))
        self.darkness_slider.setAccessibleName("Background depth")
        self.darkness_slider.setToolTip(
            "How dark the window and panels sit behind the accent colour."
        )
        self.darkness_slider.valueChanged.connect(self._on_darkness_changed)
        self.darkness_slider.sliderReleased.connect(self._apply_debounced)
        sliders_box.addWidget(self.darkness_slider)

        left_box.addLayout(sliders_box)

        read_row = QHBoxLayout()
        read_lbl = QLabel("Readability")
        read_lbl.setTextFormat(Qt.TextFormat.PlainText)
        read_lbl.setStyleSheet("font-size: 11px; font-weight: 600; color: #888888;")
        read_row.addWidget(read_lbl)
        read_row.addStretch(1)

        self.fix_btn = QPushButton("Fix")
        self.fix_btn.setProperty("primary", "true")
        # No icon: its colour bakes in, so a disabled button keeps a bright tick and
        # a light theme a white one.
        self.fix_btn.setMinimumWidth(72)
        self.fix_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fix_btn.setAccessibleName("Adjust the theme until the text reads")
        self.fix_btn.setToolTip(
            "Move the Studio's own controls until the failing pairs pass, and say "
            "what changed. Reset Defaults, or the sliders, undo it."
        )
        self.fix_btn.clicked.connect(self._fix_readability)
        read_row.addWidget(self.fix_btn)
        left_box.addLayout(read_row)

        self.contrast_summary = QLabel("")
        self.contrast_summary.setTextFormat(Qt.TextFormat.PlainText)
        self.contrast_summary.setWordWrap(True)
        self.contrast_summary.setStyleSheet("font-size: 10px; font-weight: 700;")
        left_box.addWidget(self.contrast_summary)

        self.contrast_rows: list[QLabel] = []
        rows_box = QVBoxLayout()
        rows_box.setSpacing(2)
        for _ in CONTRAST_PAIRS:
            pair_row = QLabel("")
            pair_row.setTextFormat(Qt.TextFormat.PlainText)
            pair_row.setFixedHeight(18)
            self.contrast_rows.append(pair_row)
            rows_box.addWidget(pair_row)
        left_box.addLayout(rows_box)

        self.fix_note = QLabel("")
        self.fix_note.setTextFormat(Qt.TextFormat.PlainText)
        self.fix_note.setWordWrap(True)
        self.fix_note.setStyleSheet("font-size: 10px; color: #888888;")
        self.fix_note.setVisible(False)
        left_box.addWidget(self.fix_note)
        left_box.addStretch(1)
        columns_layout.addLayout(left_box, 2)

        # The preview is what the page is for, so it takes three parts to the
        # controls' two and stretches with the window.
        self.preview_card = LiveThemePreviewCard(main_card)
        self.preview_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        columns_layout.addWidget(self.preview_card, 3)

        card_lay.addLayout(columns_layout, 1)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        self.reset_btn = QPushButton("Reset Defaults")
        self.reset_btn.setIcon(material_icon("refresh", "#888888"))
        self.reset_btn.clicked.connect(self._reset_to_defaults)
        actions_row.addWidget(self.reset_btn)

        # Restyling the window recomputes every widget, so edits are coalesced rather
        # than applied per keystroke. The preview itself keeps up in real time.
        self.live_apply_check = QCheckBox("Restyle the window as I edit")
        self.live_apply_check.setChecked(True)
        self.live_apply_check.setToolTip(
            "Apply each edit to the whole application, not just the preview. "
            "Turn it off if the pause after each change gets in the way."
        )
        actions_row.addWidget(self.live_apply_check)

        actions_row.addStretch(1)

        self.save_btn = QPushButton("Save to Gallery…")
        self.save_btn.setProperty("secondary", "true")
        self.save_btn.setIcon(material_icon("add", "#ffffff"))
        self.save_btn.setFixedHeight(34)
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.setToolTip(
            "Save these colours as a named theme. It appears in the gallery and can be "
            "edited, shared, or removed like any other."
        )
        self.save_btn.clicked.connect(self._save_to_gallery)
        actions_row.addWidget(self.save_btn)

        self.apply_btn = QPushButton("Apply to CrapCleaner")
        self.apply_btn.setToolTip(
            "Use these colours as the running theme. Saving to the gallery is "
            "separate, and is what lets you come back to it later."
        )
        self.apply_btn.setProperty("primary", "true")
        self.apply_btn.setIcon(material_icon("check", "#ffffff"))
        self.apply_btn.setFixedHeight(34)
        self.apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_btn.clicked.connect(self._apply_and_save)
        actions_row.addWidget(self.apply_btn)

        card_lay.addLayout(actions_row)
        root.addWidget(main_card, 1)

    def _populate_start_from(self) -> None:
        """List every theme, with the ones the Studio can reproduce exactly first."""
        from crapcleaner.gui.theme import THEMES, theme_generator, theme_label

        self.start_from.blockSignals(True)
        self.start_from.clear()
        self.start_from.addItem("Nothing - start from scratch", None)

        exact: list[str] = []
        approximate: list[str] = []
        for theme_id in THEMES:
            if theme_id == "custom":
                continue
            target = exact if theme_generator(theme_id) else approximate
            target.append(theme_id)

        for theme_id in exact:
            self.start_from.addItem(f"{theme_label(theme_id)} (your theme)", theme_id)
        for theme_id in approximate:
            self.start_from.addItem(theme_label(theme_id), theme_id)
        self.start_from.blockSignals(False)

    def _on_start_from(self, index: int) -> None:
        theme_id = self.start_from.itemData(index)
        if theme_id:
            self.load_theme(str(theme_id))
        else:
            self.start_note.setVisible(False)

    def load_theme(self, theme_id: str) -> bool:
        """Seed the Studio from a theme. True when it reproduces it exactly.

        A theme saved from here records the settings that made it. Anything else
        has no recipe, so its accent and canvas are taken and the rest generated
        afresh - a starting point rather than a copy, and it says so.
        """
        from crapcleaner.gui.theme import PALETTES, is_dark_theme, theme_generator, theme_label

        recipe = theme_generator(theme_id)
        if recipe:
            self._current_primary = normalize_hex(
                recipe.get("primary_color", self._current_primary)
            )
            self._current_mode = recipe.get("mode", "dark")
            self._current_mood = recipe.get("mood", "cohesive")
            self._current_contrast = float(recipe.get("surface_contrast", 1.0))
            self._current_intensity = float(recipe.get("accent_intensity", 1.0))
            self._current_bg_darkness = float(recipe.get("bg_darkness", 1.0))
            self.start_note.setText(f"Loaded {theme_label(theme_id)} exactly as it was saved.")
            self.start_note.setVisible(True)
            self._sync_controls()
            self._update_preview(auto_apply=False)
            return True

        palette = PALETTES.get(theme_id)
        if not palette:
            return False
        self._current_primary = normalize_hex(palette.get("accent", self._current_primary))
        self._current_mode = "dark" if is_dark_theme(theme_id) else "light"
        self._current_mood = "cohesive"
        self._current_contrast = 1.0
        self._current_intensity = 1.0
        self._current_bg_darkness = 1.0
        self.start_note.setText(
            f"{theme_label(theme_id)} has no Studio recipe, so its accent and canvas "
            f"were taken and the rest generated. Expect a relative, not a copy."
        )
        self.start_note.setVisible(True)
        self._sync_controls()
        self._update_preview(auto_apply=False)
        return False

    def _sync_controls(self) -> None:
        """Push the current values out to the widgets that show them."""
        self.hex_input.blockSignals(True)
        self.hex_input.setText(self._current_primary)
        self.hex_input.blockSignals(False)
        self._mark_hex_valid(True)

        self.dark_btn.setChecked(self._current_mode != "light")
        self.light_btn.setChecked(self._current_mode == "light")
        if self._current_mood in self._mood_buttons:
            self._mood_buttons[self._current_mood].setChecked(True)

        for slider, value in (
            (self.contrast_slider, self._current_contrast),
            (self.intensity_slider, self._current_intensity),
            (self.darkness_slider, self._current_bg_darkness),
        ):
            slider.blockSignals(True)
            slider.setValue(int(round(value * 100)))
            slider.blockSignals(False)
        self.contrast_val_lbl.setText(f"{int(round(self._current_contrast * 100))}%")
        self.intensity_val_lbl.setText(f"{int(round(self._current_intensity * 100))}%")
        self.darkness_val_lbl.setText(f"{int(round(self._current_bg_darkness * 100))}%")

    def _mark_hex_valid(self, valid: bool) -> None:
        """Say so when what has been typed is not a colour."""
        self.hex_input.setStyleSheet(
            "" if valid else "border: 1px solid #ef4444; border-radius: 4px;"
        )
        self.hex_input.setToolTip("" if valid else "Six hex digits, for example #3b82f6.")

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
            self._mark_hex_valid(True)
            # Typing is continuous: redraw as it is typed, restyle when it stops.
            self._request_preview()
            self._debounce_timer.start(160)
        else:
            self._mark_hex_valid(not text.strip())

    def _set_primary_color(self, hex_code: str) -> None:
        normalized = normalize_hex(hex_code)
        self._current_primary = normalized
        self.hex_input.blockSignals(True)
        self.hex_input.setText(normalized)
        self.hex_input.blockSignals(False)
        self._changed()

    def _set_mode(self, mode: str) -> None:
        self._current_mode = mode
        self._changed()

    def _set_mood(self, mood: str) -> None:
        self._current_mood = mood
        self._changed()

    def _changed(self) -> None:
        """Redraw the preview now; let the rest of the window follow.

        A restyle costs the same whether a slider or a swatch caused it, so both
        wait: clicking through presets stays instant in the preview.
        """
        self._request_preview()
        self._debounce_timer.start(160)

    def _on_contrast_changed(self, value: int) -> None:
        self._current_contrast = value / 100.0
        self.contrast_val_lbl.setText(f"{value}%")
        self._request_preview()
        self._debounce_timer.start(160)

    def _on_darkness_changed(self, value: int) -> None:
        self._current_bg_darkness = value / 100.0
        self.darkness_val_lbl.setText(f"{value}%")
        self._request_preview()
        self._debounce_timer.start(160)

    def _on_intensity_changed(self, value: int) -> None:
        self._current_intensity = value / 100.0
        self.intensity_val_lbl.setText(f"{value}%")
        self._request_preview()
        self._debounce_timer.start(160)

    def _request_preview(self) -> None:
        """Redraw now, or as soon as the last redraw has had its frame."""
        if self._preview_timer.isActive():
            self._preview_pending = True
            return
        self._update_preview(auto_apply=False, full_restyle=False)
        self._preview_timer.start()

    def _preview_cooldown(self) -> None:
        if self._preview_pending:
            self._preview_pending = False
            self._update_preview(auto_apply=False, full_restyle=False)
            self._preview_timer.start()

    def _apply_debounced(self) -> None:
        self._debounce_timer.stop()
        self._preview_pending = False
        self._update_preview(auto_apply=True, full_restyle=True)

    def _on_magic_dice_clicked(self) -> None:
        magic = generate_magic_palette()
        self._current_primary = magic["primary_color"]
        self._current_mode = magic["mode"]
        self._current_mood = magic["mood"]
        self._current_contrast = magic["surface_contrast"]
        self._current_intensity = magic["accent_intensity"]
        # Dropping the rolled depth meant the roll never produced the theme it described.
        self._current_bg_darkness = magic["bg_darkness"]

        self.start_from.setCurrentIndex(0)
        self.start_note.setVisible(False)
        self._sync_controls()
        self._update_preview(auto_apply=True)

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
        self._update_readability(palette)

        if full_restyle or auto_apply:
            self.color_swatch_btn.setStyleSheet(
                f"background-color: {self._current_primary}; border: 2px solid #ffffff; "
                f"border-radius: 18px;"
            )
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

        if auto_apply and self.live_apply_check.isChecked():
            custom_cfg = {
                "primary_color": self._current_primary,
                "mode": self._current_mode,
                "mood": self._current_mood,
                "surface_contrast": self._current_contrast,
                "accent_intensity": self._current_intensity,
                "bg_darkness": self._current_bg_darkness,
            }
            self.theme_applied.emit(custom_cfg)

    def _fix_readability(self) -> None:
        """Work the controls until the failing pairs read, and report the moves."""
        fixed, notes = plan_readability_fix(self.current_config())
        if not notes:
            self.fix_note.setText(
                "No combination of these three sliders clears every pair. A different "
                "accent, or the other canvas, will."
            )
            self.fix_note.setVisible(True)
            return

        self._current_primary = fixed["primary_color"]
        self._current_contrast = fixed["surface_contrast"]
        self._current_intensity = fixed["accent_intensity"]
        self._current_bg_darkness = fixed["bg_darkness"]
        self._sync_controls()
        self._update_preview(auto_apply=True)

        remaining = len(self.preview_card.contrast_failures())
        outcome = (
            "every pair now reads." if not remaining else f"{remaining} still below the floor."
        )
        self.fix_note.setText(f"Fixed: {', '.join(notes)} - {outcome}")
        self.fix_note.setVisible(True)

    def _update_readability(self, palette: dict[str, str]) -> None:
        """Rate every pair the running application draws."""
        report = contrast_report(palette)
        failing = sum(1 for _, _, grade in report if grade == "FAILS")
        colors = {
            "AAA": palette["success"],
            "AA": palette["text"],
            "FAILS": palette["danger"],
        }
        for pair_row, (label, ratio, grade) in zip(self.contrast_rows, report):
            pair_row.setText(f"{label}   {ratio:.2f}:1   {grade}")
            weight = 700 if grade == "FAILS" else 400
            pair_row.setStyleSheet(
                f"color: {colors[grade]}; font-size: 10px; font-weight: {weight};"
            )

        self.fix_btn.setEnabled(bool(failing))
        if failing:
            self.contrast_summary.setText(
                f"{failing} of {len(report)} fall below {MIN_PAIR_CONTRAST}:1. The "
                f"application will correct them when it loads the theme; Fix adjusts "
                f"the settings so it does not have to."
            )
            self.contrast_summary.setStyleSheet(
                f"color: {palette['danger']}; font-size: 10px; font-weight: 700;"
            )
        else:
            self.contrast_summary.setText(f"All {len(report)} pairs meet WCAG AA.")
            self.contrast_summary.setStyleSheet(
                f"color: {palette['success']}; font-size: 10px; font-weight: 700;"
            )

    def current_config(self) -> dict:
        """The Studio's settings, which are what a saved theme stores."""
        return {
            "primary_color": self._current_primary,
            "mode": self._current_mode,
            "mood": self._current_mood,
            "surface_contrast": self._current_contrast,
            "accent_intensity": self._current_intensity,
            "bg_darkness": self._current_bg_darkness,
        }

    def _save_to_gallery(self) -> None:
        """Write the current palette to the theme directory as a theme of its own."""

        from crapcleaner.gui.color_engine import generate_custom_palette
        from crapcleaner.gui.theme import PALETTES, save_user_theme, slugify

        name, accepted = QInputDialog.getText(
            self, "Save theme", "Name this theme:", text=self._suggested_name()
        )
        if not accepted or not name.strip():
            return

        theme_id = slugify(name)
        if theme_id in PALETTES:
            from crapcleaner.gui.theme import is_user_theme

            if not is_user_theme(theme_id):
                QMessageBox.warning(
                    self,
                    "Name in use",
                    f"{name!r} matches a built-in theme. Choose another name.",
                )
                return
            answer = QMessageBox.question(
                self,
                "Replace theme",
                f"You already have a theme called {name!r}. Replace it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        config = self.current_config()
        palette = generate_custom_palette(
            primary_color=self._current_primary,
            mode=self._current_mode,
            mood=self._current_mood,
            surface_contrast=self._current_contrast,
            accent_intensity=self._current_intensity,
            bg_darkness=self._current_bg_darkness,
        )
        try:
            saved_id = save_user_theme(name.strip(), palette, generator=config, theme_id=theme_id)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Could not save", str(exc))
            return

        self._populate_start_from()
        index = self.start_from.findData(saved_id)
        if index >= 0:
            self.start_from.setCurrentIndex(index)
        self.theme_saved.emit(saved_id)

    def _suggested_name(self) -> str:
        return f"{self._current_mood.title()} {self._current_primary.lstrip('#').upper()}"

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
        self.start_from.setCurrentIndex(0)
        self.start_note.setVisible(False)
        self._sync_controls()
        self._update_preview(auto_apply=True)
