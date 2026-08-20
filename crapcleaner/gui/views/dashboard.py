"""Dashboard view: live vitals, drive cards, and the latest scan summary."""

import os

from PySide6.QtCore import (
    QEasingCurve,
    Qt,
    QTimer,
    QVariantAnimation,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.gui.effects import AnimatedNumber, SegmentedBar, Sparkline, add_depth, glow
from crapcleaner.gui.icons import icon as material_icon
from crapcleaner.gui.views.common import (
    ClickableCard,
    DriveCard,
    StorageDonut,
    _c,
    badge,
    page_header,
    restyle_stat_card,
    section_label,
    stat_card,
)
from crapcleaner.history import load as load_history
from crapcleaner.models.report import ScanReport
from crapcleaner.system.live_metrics import sample_live_metrics
from crapcleaner.utils.format import (
    format_datetime,
    format_size,
)
from crapcleaner.utils.platform import (
    get_drive_info,
    is_admin,
    is_windows,
    linux_drive_display_name,
    list_drives,
)


class DashboardView(QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self._main = main
        self._theme = "dark"
        self._used_fraction = 0.0
        #: Last scan report, kept so a theme change can redraw the breakdown rows.
        self._last_report: ScanReport | None = None
        self._build()

    def _open_memory_cleaner(self) -> None:
        navigate = getattr(self._main, "navigate", None)
        if callable(navigate):
            navigate("memory")

    def _build(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(14)
        layout.addWidget(
            page_header(
                "System Overview & Health",
                "Inspect disk storage, identify junk, and safely reclaim gigabytes in seconds.",
            )
        )

        content = QHBoxLayout()
        content.setSpacing(14)

        hero = QFrame()
        hero.setProperty("card", "true")
        hero_lay = QVBoxLayout(hero)
        hero_lay.setContentsMargins(22, 20, 22, 20)
        hero_lay.setSpacing(8)

        hero_top = QHBoxLayout()
        hero_top.addWidget(section_label("Potential Reclaimable Space"))
        hero_top.addStretch(1)
        self.status_badge = badge("Ready to scan", "accent")
        hero_top.addWidget(self.status_badge)
        hero_lay.addLayout(hero_top)

        # Counting up on a scan result is the one place motion earns its keep.
        self.reclaimable_label = AnimatedNumber(formatter=format_size)
        self.reclaimable_label.setText("Not scanned yet")
        self.reclaimable_label.setProperty("heroValue", "true")
        self.reclaimable_label.setStyleSheet(
            f"font-size: 32px; font-weight: 800; color: {_c(self._theme, 'text')};"
        )
        hero_lay.addWidget(self.reclaimable_label)

        self.last_scan_label = QLabel("Last scan: never")
        self.last_cleanup_label = QLabel("Last cleanup: never")
        for lbl in (self.last_scan_label, self.last_cleanup_label):
            lbl.setProperty("subtle", "true")
            hero_lay.addWidget(lbl)

        hero_lay.addSpacing(6)
        self.admin_label = QLabel()
        self.admin_label.setWordWrap(True)
        self.admin_label.setProperty("subtle", "true")
        hero_lay.addWidget(self.admin_label)

        hero_lay.addSpacing(10)
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        # Qt clips a QGraphicsEffect to the widget's own rect, so the primary button's
        # halo needs a few pixels of room around the row or it is never seen.
        buttons.setContentsMargins(0, 6, 0, 6)
        self.scan_button = QPushButton("Scan for Crap")
        self.scan_button.setProperty("primary", "true")
        self.scan_button.setIcon(material_icon("search", "#ffffff"))
        self.scan_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scan_button.setFixedHeight(34)
        self.scan_button.clicked.connect(self._main.start_scan)

        self.cancel_button = QPushButton("Cancel Scan")
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.setFixedHeight(34)
        self.cancel_button.hide()
        self.cancel_button.clicked.connect(self._cancel_scan)

        self.review_button = QPushButton("Review && Clean")
        self.review_button.setProperty("danger", "true")
        self.review_button.setIcon(material_icon("clean", "#ffffff"))
        self.review_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.review_button.setFixedHeight(34)
        self.review_button.setEnabled(False)
        self.review_button.setToolTip("Go to Cleanup with safe categories pre-selected.")
        self.review_button.clicked.connect(self._main.review_and_clean)

        buttons.addWidget(self.scan_button)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.review_button)
        buttons.addStretch(1)
        hero_lay.addLayout(buttons)
        # The primary action is the one thing on this page a new user must find.
        glow(self.scan_button, self._theme)

        self.scan_progress = QProgressBar()
        self.scan_progress.setRange(0, 100)
        self.scan_progress.setValue(0)
        self.scan_progress.setTextVisible(True)
        self.scan_progress.setFormat("Scanning...")
        self.scan_progress.setFixedHeight(22)
        self.scan_progress.setVisible(False)
        hero_lay.addWidget(self.scan_progress)

        content.addWidget(hero, 1)

        donut_card = QFrame()
        donut_card.setProperty("card", "true")
        donut_card.setFixedWidth(260)
        donut_lay = QVBoxLayout(donut_card)
        donut_lay.setContentsMargins(18, 16, 18, 16)
        donut_lay.setSpacing(6)
        donut_lay.addWidget(section_label("Selected Drive Usage"))
        donut_lay.addSpacing(4)
        self.donut = StorageDonut()
        donut_lay.addWidget(self.donut, 0, Qt.AlignmentFlag.AlignCenter)
        self.drive_detail = QLabel()
        self.drive_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drive_detail.setWordWrap(True)
        self.drive_detail.setProperty("subtle", "true")
        donut_lay.addWidget(self.drive_detail)
        content.addWidget(donut_card, 0, Qt.AlignmentFlag.AlignTop)

        layout.addLayout(content)

        layout.addWidget(section_label("Live System Vitals"))
        vitals_row = QHBoxLayout()
        vitals_row.setSpacing(12)

        self.ram_card = ClickableCard()
        self.ram_card.setProperty("card", "true")
        self.ram_card.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ram_card.setToolTip("Click to open Memory Cleaner")
        self.ram_card.clicked.connect(self._open_memory_cleaner)
        rc_lay = QVBoxLayout(self.ram_card)
        rc_lay.setContentsMargins(14, 12, 14, 12)
        rc_lay.setSpacing(6)

        rc_top = QHBoxLayout()
        rc_title = QLabel("Memory (RAM)")
        rc_title.setProperty("subtle", "true")
        rc_top.addWidget(rc_title)
        rc_top.addStretch(1)
        self.ram_badge = badge("NORMAL", "safe")
        rc_top.addWidget(self.ram_badge)
        rc_lay.addLayout(rc_top)

        self.ram_val = QLabel("-- / --")
        self.ram_val.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {_c(self._theme, 'text')};"
        )
        rc_lay.addWidget(self.ram_val)

        self.ram_bar = QProgressBar()
        self.ram_bar.setRange(0, 100)
        self.ram_bar.setValue(0)
        self.ram_bar.setTextVisible(False)
        self.ram_bar.setFixedHeight(5)
        self.ram_bar.setProperty("thin", "true")
        self.ram_bar.setProperty("good", "true")
        rc_lay.addWidget(self.ram_bar)

        # Sparklines share the vitals tick below, so no card owns a timer of its own.
        self.ram_spark = Sparkline(self._theme, "accent")
        rc_lay.addWidget(self.ram_spark)

        self.ram_sub = QLabel("Click to open Memory Cleaner ->")
        self.ram_sub.setProperty("subtle", "true")
        self.ram_sub.setStyleSheet(f"font-size: 10px; color: {_c(self._theme, 'muted')};")
        rc_lay.addWidget(self.ram_sub)
        vitals_row.addWidget(self.ram_card, 1)

        self.cpu_card = QFrame()
        self.cpu_card.setProperty("card", "true")
        cpu_lay = QVBoxLayout(self.cpu_card)
        cpu_lay.setContentsMargins(14, 12, 14, 12)
        cpu_lay.setSpacing(6)

        cpu_top = QHBoxLayout()
        cpu_title = QLabel("Processor (CPU)")
        cpu_title.setProperty("subtle", "true")
        cpu_top.addWidget(cpu_title)
        cpu_top.addStretch(1)
        self.cpu_badge = badge(f"{os.cpu_count() or 4} Cores", "accent")
        cpu_top.addWidget(self.cpu_badge)
        cpu_lay.addLayout(cpu_top)

        self.cpu_val = QLabel("-- % Load")
        self.cpu_val.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {_c(self._theme, 'text')};"
        )
        cpu_lay.addWidget(self.cpu_val)

        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setValue(0)
        self.cpu_bar.setTextVisible(False)
        self.cpu_bar.setFixedHeight(5)
        self.cpu_bar.setProperty("thin", "true")
        self.cpu_bar.setProperty("good", "true")
        cpu_lay.addWidget(self.cpu_bar)

        self.cpu_spark = Sparkline(self._theme, "info")
        cpu_lay.addWidget(self.cpu_spark)

        self.cpu_sub = QLabel("Uptime: -- · AC Power")
        self.cpu_sub.setProperty("subtle", "true")
        self.cpu_sub.setStyleSheet(f"font-size: 10px; color: {_c(self._theme, 'muted')};")
        cpu_lay.addWidget(self.cpu_sub)
        vitals_row.addWidget(self.cpu_card, 1)

        self.gpu_card = QFrame()
        self.gpu_card.setProperty("card", "true")
        gpu_lay = QVBoxLayout(self.gpu_card)
        gpu_lay.setContentsMargins(14, 12, 14, 12)
        gpu_lay.setSpacing(6)

        gpu_top = QHBoxLayout()
        gpu_title = QLabel("Graphics (GPU)")
        gpu_title.setProperty("subtle", "true")
        gpu_top.addWidget(gpu_title)
        gpu_top.addStretch(1)
        self.gpu_badge = badge("OPTIMAL", "safe")
        gpu_top.addWidget(self.gpu_badge)
        gpu_lay.addLayout(gpu_top)

        self.gpu_val = QLabel("--")
        self.gpu_val.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {_c(self._theme, 'text')};"
        )
        gpu_lay.addWidget(self.gpu_val)

        self.gpu_bar = QProgressBar()
        self.gpu_bar.setRange(0, 100)
        self.gpu_bar.setValue(0)
        self.gpu_bar.setTextVisible(False)
        self.gpu_bar.setFixedHeight(5)
        self.gpu_bar.setProperty("thin", "true")
        self.gpu_bar.setProperty("good", "true")
        gpu_lay.addWidget(self.gpu_bar)

        self.gpu_spark = Sparkline(self._theme, "success")
        gpu_lay.addWidget(self.gpu_spark)

        self.gpu_sub = QLabel("VRAM: -- / --")
        self.gpu_sub.setProperty("subtle", "true")
        self.gpu_sub.setStyleSheet(f"font-size: 10px; color: {_c(self._theme, 'muted')};")
        gpu_lay.addWidget(self.gpu_sub)
        vitals_row.addWidget(self.gpu_card, 1)

        self.net_card = QFrame()
        self.net_card.setProperty("card", "true")
        net_lay = QVBoxLayout(self.net_card)
        net_lay.setContentsMargins(14, 12, 14, 12)
        net_lay.setSpacing(6)

        net_top = QHBoxLayout()
        net_title = QLabel("Network Activity")
        net_title.setProperty("subtle", "true")
        net_top.addWidget(net_title)
        net_top.addStretch(1)
        self.net_badge = badge("Connected", "accent")
        net_top.addWidget(self.net_badge)
        net_lay.addLayout(net_top)

        net_rates_row = QHBoxLayout()
        net_rates_row.setSpacing(8)

        self.net_in_label = QLabel("↓ 0 B/s")
        self.net_in_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {_c(self._theme, 'safe')};"
        )
        self.net_out_label = QLabel("↑ 0 B/s")
        self.net_out_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {_c(self._theme, 'accent')};"
        )
        net_rates_row.addWidget(self.net_in_label)
        net_rates_row.addWidget(self.net_out_label)
        net_rates_row.addStretch(1)
        net_lay.addLayout(net_rates_row)

        # Throughput has no natural ceiling, so this sparkline auto-scales to its peak.
        self.net_spark = Sparkline(self._theme, "safe")
        self.net_spark.set_ceiling(0)
        net_lay.addWidget(self.net_spark)

        self.net_sub = QLabel("Session: 0 B in · 0 B out")
        self.net_sub.setProperty("subtle", "true")
        self.net_sub.setStyleSheet(f"font-size: 10px; color: {_c(self._theme, 'muted')};")
        net_lay.addWidget(self.net_sub)
        vitals_row.addWidget(self.net_card, 1)

        layout.addLayout(vitals_row)

        self._vitals_timer = QTimer(self)
        self._vitals_timer.setInterval(1200)
        self._vitals_timer.timeout.connect(self._update_live_vitals)

        layout.addWidget(section_label("System Metrics & Categories"))
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)

        self.c1, self.c1_val, self.c1_sub = stat_card(
            "Safe Caches", "--", "Temporary files & browser caches", self._theme
        )
        self.c2, self.c2_val, self.c2_sub = stat_card(
            "Dev & AI Caches", "--", "Python, Docker & AI models", self._theme
        )
        self.c3, self.c3_val, self.c3_sub = stat_card(
            "Drives Detected", "--", "Monitored storage volumes", self._theme
        )
        self.c4, self.c4_val, self.c4_sub = stat_card(
            "Lifetime Cleaned", "--", "Recovered across sessions", self._theme
        )

        stats_row.addWidget(self.c1)
        stats_row.addWidget(self.c2)
        stats_row.addWidget(self.c3)
        stats_row.addWidget(self.c4)
        layout.addLayout(stats_row)

        layout.addWidget(section_label("Drives & Partitions"))

        self.drives = [d.rstrip("\\") if is_windows() else d for d in list_drives()]
        self._selected_drive = self.drives[0] if self.drives else ("C:" if is_windows() else "/")
        self._cards = {}

        cards_scroll = QScrollArea()
        cards_scroll.setWidgetResizable(True)
        cards_scroll.setFrameShape(QFrame.Shape.NoFrame)
        cards_scroll.setFixedHeight(150)
        cards_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        cards_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        cards_container = QWidget()
        cards_row = QHBoxLayout(cards_container)
        cards_row.setContentsMargins(0, 0, 0, 0)
        cards_row.setSpacing(12)
        for drive in self.drives:
            card = DriveCard(drive)
            card.clicked.connect(self._select_drive)
            # Painted hover rather than a graphics effect: these repeat inside a scroll
            # area, where an offscreen pixmap per card costs a repaint each.
            add_depth(card, self._theme, "card")
            cards_row.addWidget(card)
            self._cards[drive] = card
        cards_row.addStretch(1)
        cards_scroll.setWidget(cards_container)
        layout.addWidget(cards_scroll)

        # Previews the categories a scan would check, so this is never blank before a first run.
        layout.addWidget(section_label("Reclaimable Breakdown"))
        self.breakdown_card = QFrame()
        self.breakdown_card.setProperty("card", "true")
        bd_lay = QVBoxLayout(self.breakdown_card)
        bd_lay.setContentsMargins(18, 16, 18, 16)
        bd_lay.setSpacing(10)

        bd_top = QHBoxLayout()
        self.breakdown_total = AnimatedNumber(formatter=format_size)
        self.breakdown_total.setText("Not scanned yet")
        self.breakdown_total.setStyleSheet(
            f"font-size: 18px; font-weight: 800; color: {_c(self._theme, 'text')};"
        )
        bd_top.addWidget(self.breakdown_total)
        bd_top.addStretch(1)
        self.breakdown_badge = badge("PREVIEW", "muted")
        bd_top.addWidget(self.breakdown_badge)
        bd_lay.addLayout(bd_top)

        self.breakdown_bar = SegmentedBar(self._theme, height=12)
        bd_lay.addWidget(self.breakdown_bar)

        self.breakdown_rows = QVBoxLayout()
        self.breakdown_rows.setSpacing(4)
        bd_lay.addLayout(self.breakdown_rows)

        layout.addWidget(self.breakdown_card)
        self._show_breakdown_preview()

        layout.addStretch(1)

        scroll.setWidget(container)
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.addWidget(scroll)

    def _cancel_scan(self):
        if hasattr(self._main, "cancel_active_scan"):
            self._main.cancel_active_scan()

    def refresh(self):
        for drive, card in self._cards.items():
            try:
                card.set_data(get_drive_info(drive))
            except OSError:
                card.set_data(None)
        self._select_drive(self._selected_drive)
        self.admin_label.setText(
            "Running with Administrator privileges."
            if is_admin()
            else "Running as Standard User. Some system categories may require elevation."
        )
        self.admin_label.setStyleSheet(
            f"color: {_c(self._theme, 'success' if is_admin() else 'muted')}; font-size: 12px;"
        )

        self.c3_val.setText(f"{len(self.drives)} Drives")
        self.c3_sub.setText(f"Active: {self._selected_drive}")

        entries = load_history()
        total_rec = sum(e.space_recovered for e in entries if not e.dry_run)
        self.c4_val.setText(format_size(total_rec))
        self.c4_sub.setText(f"{len(entries)} total actions logged")
        self._update_live_vitals()

    def _select_drive(self, drive: str):
        if drive not in self._cards:
            return
        self._selected_drive = drive
        for d, card in self._cards.items():
            card.set_selected(d == drive)
        try:
            info = get_drive_info(drive)
            total = int(info.get("total", 0))
            used = int(info.get("used", 0))
            free = int(info.get("free", 0))
            self._used_fraction = used / total if total else 0.0
            self.donut.set_usage(self._used_fraction, self._theme)
            label = str(info.get("label", ""))
            fs_name = str(info.get("filesystem", ""))
            extra = []
            if label:
                extra.append(label)
            if fs_name:
                extra.append(fs_name)
            extra_line = (
                f"<br><span style='font-size:11px'>{' · '.join(extra)}</span>" if extra else ""
            )
            drive_name = drive if is_windows() else linux_drive_display_name(drive)
            path_line = "" if is_windows() else f"<br><span style='font-size:11px'>{drive}</span>"
            self.drive_detail.setText(
                f"<b>{drive_name}</b>{path_line}<br>"
                f"Used: {format_size(used)} · Free: {format_size(free)} · Total: {format_size(total)}"
                f"{extra_line}"
            )
        except OSError:
            self._used_fraction = 0.0
            self.donut.set_usage(0.0, self._theme)
            self.drive_detail.setText(f"{drive}<br>Unavailable")
        self.drive_detail.setStyleSheet(f"color: {_c(self._theme, 'muted')};")

    #: Safety level -> palette token, so a row is coloured by how risky it is to clean.
    # `safe` and `success` are the same green in most palettes, so LOW_RISK takes `info`.
    _BREAKDOWN_TOKENS = {
        "SAFE": "safe",
        "LOW_RISK": "info",
        "REVIEW": "review",
        "DANGEROUS": "danger",
    }

    def _clear_breakdown_rows(self) -> None:
        while self.breakdown_rows.count():
            item = self.breakdown_rows.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

    def _breakdown_row(self, token: str, name: str, detail: str, dim: bool = False) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        swatch = QLabel()
        swatch.setFixedSize(10, 10)
        swatch.setStyleSheet(
            f"background-color: {_c(self._theme, 'faint' if dim else token)}; border-radius: 3px;"
        )
        lay.addWidget(swatch)

        label = QLabel(name)
        label.setStyleSheet(
            f"font-size: 11px; color: {_c(self._theme, 'muted' if dim else 'text')};"
        )
        lay.addWidget(label)
        lay.addStretch(1)

        value = QLabel(detail)
        value.setStyleSheet(
            f"font-size: 11px; font-weight: {'600' if not dim else '400'}; "
            f"color: {_c(self._theme, 'muted' if dim else 'text')};"
        )
        lay.addWidget(value)
        return row

    def _show_breakdown_preview(self) -> None:
        """Before any scan, list what a scan would look at rather than showing nothing."""
        self._clear_breakdown_rows()
        categories = getattr(self._main, "_categories", None) or []

        groups: list[str] = []
        for category in categories:
            group = getattr(category, "group", "") or "Other"
            if group not in groups:
                groups.append(group)
        preview = groups[:5]

        # Stop any in-flight count-up before overwriting the text, or it would tick
        # straight back over "Not scanned yet".
        self.breakdown_total.stop()
        self.breakdown_total.set_value(0)
        self.breakdown_total.setText("Not scanned yet")
        self.breakdown_badge.setText("PREVIEW")
        self.breakdown_badge.setProperty("level", "muted")
        self.breakdown_badge.style().unpolish(self.breakdown_badge)
        self.breakdown_badge.style().polish(self.breakdown_badge)

        if not preview:
            self.breakdown_bar.set_segments([], muted=True)
            self.breakdown_rows.addWidget(
                self._breakdown_row("faint", "No categories enabled", "", dim=True)
            )
            return

        # Equal-width placeholder segments: the categories are known, the sizes are not.
        self.breakdown_bar.set_segments([(name, 1.0, "faint") for name in preview], muted=True)
        for name in preview:
            self.breakdown_rows.addWidget(
                self._breakdown_row("faint", name, "not scanned", dim=True)
            )

        # Count groups, not categories: the rows above are groups.
        summary = f"{len(categories)} categories across {len(groups)} groups ready to scan"
        self.breakdown_rows.addWidget(self._breakdown_row("faint", summary, "", dim=True))

    def _show_breakdown_results(self, report: ScanReport) -> None:
        self._last_report = report
        self._clear_breakdown_rows()
        found = sorted(
            (r for r in report.results if r.size > 0), key=lambda r: r.size, reverse=True
        )

        self.breakdown_total.animate_to(report.total_size)
        self.breakdown_badge.setText(f"{len(found)} CATEGORIES")
        self.breakdown_badge.setProperty("level", "accent" if found else "muted")
        self.breakdown_badge.style().unpolish(self.breakdown_badge)
        self.breakdown_badge.style().polish(self.breakdown_badge)

        if not found:
            self.breakdown_bar.set_segments([], muted=True)
            self.breakdown_rows.addWidget(
                self._breakdown_row("safe", "Nothing to reclaim - system is clean", "", dim=True)
            )
            return

        top = found[:5]
        segments = [
            (r.name, float(r.size), self._BREAKDOWN_TOKENS.get(str(r.safety_level), "accent"))
            for r in top
        ]
        others = sum(r.size for r in found[5:])
        if others > 0:
            segments.append(("Other categories", float(others), "muted"))

        self.breakdown_bar.set_segments(segments)
        for result in top:
            token = self._BREAKDOWN_TOKENS.get(str(result.safety_level), "accent")
            self.breakdown_rows.addWidget(
                self._breakdown_row(token, result.name, format_size(result.size))
            )
        if others > 0:
            self.breakdown_rows.addWidget(
                self._breakdown_row(
                    "muted", f"{len(found) - len(top)} other categories", format_size(others)
                )
            )

    def set_scan(self, report: ScanReport):
        self._show_breakdown_results(report)
        self.reclaimable_label.animate_to(report.total_size)
        categories = [r for r in report.results if r.size > 0]
        self.last_scan_label.setText(
            f"Last scan: {format_datetime(report.started)} · {len(categories)} categories identified"
        )
        self.status_badge.setText("Scan Complete")
        self.status_badge.setProperty("level", "safe" if report.total_size > 0 else "accent")
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

        safe_total = sum(r.size for r in report.results if r.safety_level in ("SAFE", "LOW_RISK"))
        self.c1_val.setText(format_size(safe_total))

        dev_total = sum(
            r.size
            for r in report.results
            if r.group in ("Python", "Node.js", ".NET", "Developer tools", "AI", "Docker")
        )
        self.c2_val.setText(format_size(dev_total))
        self.review_button.setEnabled(report.total_size > 0)

    def set_cleanup(self, text: str):
        self.last_cleanup_label.setText(f"Last cleanup: {text}")

    def set_scanning(self, scanning: bool):
        self.scan_button.setEnabled(not scanning)
        self.cancel_button.setVisible(scanning)
        if scanning:
            self.review_button.setEnabled(False)
            self.scan_progress.setRange(0, 100)
            self.scan_progress.setValue(0)
            self.scan_progress.setFormat("Scanning system...")
            self.scan_progress.setVisible(True)
            self.status_badge.setText("Scanning...")
            self.status_badge.setProperty("level", "warn")
        else:
            self.scan_progress.setVisible(False)
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

    def set_scan_progress(self, name: str, pct: int):
        if pct < 0:
            self.scan_progress.setRange(0, 0)
            self.scan_progress.setFormat(f"Scanning: {name}")
        else:
            self.scan_progress.setRange(0, 100)
            self.scan_progress.setValue(pct)
            self.scan_progress.setFormat(f"Scanning: {name} ({pct}%)")
        self.scan_progress.setVisible(True)

    def _animate_bar(self, bar: QProgressBar, target_val: int, anim_attr: str):
        existing = getattr(self, anim_attr, None)
        if existing is not None and existing.state() == QVariantAnimation.State.Running:
            existing.stop()
        curr = bar.value()
        if curr == target_val:
            return
        anim = QVariantAnimation(self)
        anim.setDuration(550)
        anim.setStartValue(curr)
        anim.setEndValue(target_val)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.valueChanged.connect(lambda v: bar.setValue(int(v)))
        setattr(self, anim_attr, anim)
        anim.start()

    def _push_sparklines(self, snap) -> None:
        """Feed one live sample into each vitals sparkline.

        Percentages plot against a fixed 0-100 ceiling so the shape is comparable over
        time; network throughput has no ceiling and auto-scales to its own peak.
        """
        self.ram_spark.push(snap.ram.percent_used)
        self.cpu_spark.push(snap.cpu.percent_used)
        # Track the same figure the GPU bar shows, so the two agree.
        self.gpu_spark.push(snap.gpu.utilization_pct or 0.0)
        self.net_spark.push(snap.network.bytes_in_sec + snap.network.bytes_out_sec)

    def _update_live_vitals(self):
        if not self.isVisible():
            return
        try:
            snap = sample_live_metrics()
            self._push_sparklines(snap)

            ram_pct = int(snap.ram.percent_used)
            self.ram_val.setText(f"{snap.ram.used_str} / {snap.ram.total_str} ({ram_pct}%)")
            self._animate_bar(self.ram_bar, ram_pct, "_ram_anim")

            pressure = snap.ram.pressure
            if getattr(self, "_last_ram_level", None) != pressure:
                self._last_ram_level = pressure
                if pressure == "critical":
                    self.ram_badge.setText("CRITICAL")
                    self.ram_badge.setProperty("level", "danger")
                    self.ram_bar.setProperty("good", "false")
                    self.ram_bar.setProperty("warn", "false")
                    self.ram_bar.setProperty("bad", "true")
                elif pressure == "high":
                    self.ram_badge.setText("HIGH USAGE")
                    self.ram_badge.setProperty("level", "warn")
                    self.ram_bar.setProperty("good", "false")
                    self.ram_bar.setProperty("warn", "true")
                    self.ram_bar.setProperty("bad", "false")
                elif pressure == "moderate":
                    self.ram_badge.setText("MODERATE")
                    self.ram_badge.setProperty("level", "review")
                    self.ram_bar.setProperty("good", "true")
                    self.ram_bar.setProperty("warn", "false")
                    self.ram_bar.setProperty("bad", "false")
                else:
                    self.ram_badge.setText("NORMAL")
                    self.ram_badge.setProperty("level", "safe")
                    self.ram_bar.setProperty("good", "true")
                    self.ram_bar.setProperty("warn", "false")
                    self.ram_bar.setProperty("bad", "false")
                self.ram_badge.style().unpolish(self.ram_badge)
                self.ram_badge.style().polish(self.ram_badge)
                self.ram_bar.style().unpolish(self.ram_bar)
                self.ram_bar.style().polish(self.ram_bar)

            cpu_pct = int(snap.cpu.percent_used)
            self.cpu_val.setText(f"{snap.cpu.percent_used:.1f}% Load")
            self._animate_bar(self.cpu_bar, cpu_pct, "_cpu_anim")
            if snap.uptime_str:
                self.cpu_sub.setText(f"Uptime: {snap.uptime_str} · {snap.power_str}")

            cpu_level = "bad" if cpu_pct >= 85 else ("warn" if cpu_pct >= 60 else "good")
            if getattr(self, "_last_cpu_level", None) != cpu_level:
                self._last_cpu_level = cpu_level
                self.cpu_bar.setProperty("good", "true" if cpu_level == "good" else "false")
                self.cpu_bar.setProperty("warn", "true" if cpu_level == "warn" else "false")
                self.cpu_bar.setProperty("bad", "true" if cpu_level == "bad" else "false")
                self.cpu_bar.style().unpolish(self.cpu_bar)
                self.cpu_bar.style().polish(self.cpu_bar)

            if snap.gpu.available:
                self.gpu_val.setText(f"{snap.gpu.name} · {snap.gpu.temp_str}")
                gpu_load = int(snap.gpu.utilization_pct or 0)
                self._animate_bar(self.gpu_bar, gpu_load, "_gpu_anim")
                vram_pct = f" ({int(snap.gpu.vram_percent)}%)" if snap.gpu.vram_total_bytes else ""
                self.gpu_sub.setText(
                    f"VRAM: {snap.gpu.vram_fraction_str}{vram_pct} · Load: {snap.gpu.utilization_str}"
                )

                t_status = snap.gpu.thermal_status
                if getattr(self, "_last_gpu_status", None) != t_status:
                    self._last_gpu_status = t_status
                    if t_status == "hot":
                        self.gpu_badge.setText(f"{snap.gpu.temp_str} HOT")
                        self.gpu_badge.setProperty("level", "danger")
                        self.gpu_bar.setProperty("good", "false")
                        self.gpu_bar.setProperty("warn", "false")
                        self.gpu_bar.setProperty("bad", "true")
                    elif t_status == "warm":
                        self.gpu_badge.setText(f"{snap.gpu.temp_str} WARM")
                        self.gpu_badge.setProperty("level", "warn")
                        self.gpu_bar.setProperty("good", "false")
                        self.gpu_bar.setProperty("warn", "true")
                        self.gpu_bar.setProperty("bad", "false")
                    else:
                        self.gpu_badge.setText(f"{snap.gpu.temp_str} {t_status.upper()}")
                        self.gpu_badge.setProperty("level", "safe")
                        self.gpu_bar.setProperty("good", "true")
                        self.gpu_bar.setProperty("warn", "false")
                        self.gpu_bar.setProperty("bad", "false")
                    self.gpu_badge.style().unpolish(self.gpu_badge)
                    self.gpu_badge.style().polish(self.gpu_badge)
                    self.gpu_bar.style().unpolish(self.gpu_bar)
                    self.gpu_bar.style().polish(self.gpu_bar)
            else:
                self.gpu_val.setText("Display Adapter")
                self.gpu_badge.setText("READY")
                self.gpu_sub.setText(f"System: {snap.uptime_str} · {snap.power_str}")

            self.net_in_label.setText(f"↓ {snap.network.in_rate_str}")
            self.net_out_label.setText(f"↑ {snap.network.out_rate_str}")
            self.net_sub.setText(
                f"Session: {snap.network.total_in_str} in · {snap.network.total_out_str} out"
            )
            if snap.network.interface_name:
                self.net_badge.setText(snap.network.interface_name[:16])
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, "_vitals_timer") and not self._vitals_timer.isActive():
            self._vitals_timer.start()
            self._update_live_vitals()

    def hideEvent(self, event):
        super().hideEvent(event)
        if hasattr(self, "_vitals_timer") and self._vitals_timer.isActive():
            self._vitals_timer.stop()

    def apply_theme(self, theme: str):
        self._theme = theme
        for card in self._cards.values():
            card.apply_theme(theme)
        self.drive_detail.setStyleSheet(f"color: {_c(theme, 'muted')};")
        self.donut.set_usage(self._used_fraction, theme)
        self.reclaimable_label.setStyleSheet(
            f"font-size: 32px; font-weight: 800; color: {_c(theme, 'text')};"
        )
        self.ram_val.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {_c(theme, 'text')};"
        )
        self.cpu_val.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {_c(theme, 'text')};"
        )
        self.gpu_val.setStyleSheet(
            f"font-size: 15px; font-weight: 800; color: {_c(theme, 'text')};"
        )
        self.net_in_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {_c(theme, 'safe')};"
        )
        self.net_out_label.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {_c(theme, 'accent')};"
        )
        self.ram_sub.setStyleSheet(f"font-size: 10px; color: {_c(theme, 'muted')};")
        self.cpu_sub.setStyleSheet(f"font-size: 10px; color: {_c(theme, 'muted')};")
        self.gpu_sub.setStyleSheet(f"font-size: 10px; color: {_c(theme, 'muted')};")
        self.net_sub.setStyleSheet(f"font-size: 10px; color: {_c(theme, 'muted')};")

        for pair in (
            (self.c1_val, self.c1_sub),
            (self.c2_val, self.c2_sub),
            (self.c3_val, self.c3_sub),
            (self.c4_val, self.c4_sub),
        ):
            restyle_stat_card(pair[0], pair[1], theme)

        # Same baked-in-stylesheet problem as the stat cards.
        self.admin_label.setStyleSheet(
            f"color: {_c(theme, 'success' if is_admin() else 'muted')}; font-size: 12px;"
        )

        # Custom-painted widgets read the palette directly, so they need telling.
        for spark in (self.ram_spark, self.cpu_spark, self.gpu_spark, self.net_spark):
            spark.apply_theme(theme)
        self.breakdown_bar.apply_theme(theme)
        self.breakdown_total.setStyleSheet(
            f"font-size: 18px; font-weight: 800; color: {_c(theme, 'text')};"
        )
        glow(self.scan_button, theme)
        # Rebuild the breakdown rows so their swatches pick up the new palette.
        if self._last_report is not None:
            self._show_breakdown_results(self._last_report)
        else:
            self._show_breakdown_preview()
