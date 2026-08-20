"""Memory cleaner view."""

from PySide6.QtCore import (
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crapcleaner.gui.icons import icon as material_icon
from crapcleaner.gui.views.common import _c, badge, page_header, section_label, stat_card
from crapcleaner.system.memory_actions import available_actions as available_memory_actions
from crapcleaner.system.memory_actions import get_action as get_memory_action
from crapcleaner.utils.format import (
    format_size,
)
from crapcleaner.utils.platform import (
    elevate,
    is_admin,
    is_windows,
)


class MemoryView(QWidget):
    """RAM, swap, and graphics memory reporting with safe reclamation actions."""

    def __init__(self, main, parent=None):
        super().__init__(parent)
        self._main = main
        self._theme = "dark"
        self._report = None
        self._busy = False
        self._action_rows = {}
        self._action_cards = {}
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)
        root.addWidget(
            page_header(
                "Memory Cleaner",
                "Inspect physical memory, swap, and graphics VRAM, then safely optimize and reclaim memory across active processes.",
            )
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(14)

        # 1. Top Hero Card: Status, Usage Gauge & Quick Flush Action
        self.hero_card = QFrame()
        self.hero_card.setProperty("card", "true")
        hero_lay = QVBoxLayout(self.hero_card)
        hero_lay.setContentsMargins(18, 16, 18, 16)
        hero_lay.setSpacing(10)

        hero_top = QHBoxLayout()
        self.hero_badge = badge("NORMAL PRESSURE", "safe")
        self.elevated_badge = badge(
            "ELEVATED (ADMIN)" if is_admin() else "STANDARD USER",
            "accent" if is_admin() else "muted",
        )
        hero_top.addWidget(self.hero_badge)
        hero_top.addWidget(self.elevated_badge)
        hero_top.addStretch(1)

        if not is_admin() and is_windows():
            self.elevate_btn = QPushButton("Relaunch as Admin (Full Standby Flush)")
            self.elevate_btn.setProperty("secondary", "true")
            self.elevate_btn.setIcon(material_icon("security", _c(self._theme, "accent")))
            self.elevate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.elevate_btn.clicked.connect(self._relaunch_admin)
            hero_top.addWidget(self.elevate_btn)

        self.flush_btn = QPushButton("Quick Flush Memory")
        self.flush_btn.setProperty("primary", "true")
        self.flush_btn.setIcon(material_icon("bolt", "#ffffff"))
        self.flush_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.flush_btn.clicked.connect(lambda: self._run_action("flush_all"))

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setIcon(material_icon("refresh", _c(self._theme, "text")))
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh)

        hero_top.addWidget(self.flush_btn)
        hero_top.addWidget(self.refresh_btn)
        hero_lay.addLayout(hero_top)

        self.hero_title = QLabel("-- / -- Used")
        self.hero_title.setStyleSheet(
            f"font-size: 24px; font-weight: 800; color: {_c(self._theme, 'text')};"
        )
        hero_lay.addWidget(self.hero_title)

        self.ram_bar = QProgressBar()
        self.ram_bar.setRange(0, 100)
        self.ram_bar.setValue(0)
        self.ram_bar.setFixedHeight(8)
        self.ram_bar.setTextVisible(False)
        self.ram_bar.setProperty("good", "true")
        hero_lay.addWidget(self.ram_bar)

        hero_sub_row = QHBoxLayout()
        self.status_label = QLabel("Reading memory statistics...")
        self.status_label.setProperty("subtle", "true")
        self.status_label.setStyleSheet(f"font-size: 11px; color: {_c(self._theme, 'muted')};")
        self.pressure_label = QLabel("Memory pressure: normal")
        self.pressure_label.setProperty("subtle", "true")
        self.pressure_label.setStyleSheet(f"font-size: 11px; color: {_c(self._theme, 'muted')};")
        hero_sub_row.addWidget(self.status_label)
        hero_sub_row.addStretch(1)
        hero_sub_row.addWidget(self.pressure_label)
        hero_lay.addLayout(hero_sub_row)

        # Embedded result banner
        self.result_banner = QFrame()
        self.result_banner.setProperty("card", "true")
        self.result_banner.setVisible(False)
        rb_lay = QHBoxLayout(self.result_banner)
        rb_lay.setContentsMargins(12, 8, 12, 8)
        self.result_icon = QLabel()
        self.result_icon.setPixmap(material_icon("check", _c(self._theme, "safe")).pixmap(18, 18))
        self.result_label = QLabel("")
        self.result_label.setStyleSheet(f"font-weight: 600; color: {_c(self._theme, 'text')};")
        self.result_label.setWordWrap(True)
        rb_lay.addWidget(self.result_icon)
        rb_lay.addWidget(self.result_label, 1)
        hero_lay.addWidget(self.result_banner)

        layout.addWidget(self.hero_card)

        # 2. Hardware & Memory Breakdown Cards (RAM 4-metric grid, Swap Card, GPU VRAM Card)
        layout.addWidget(section_label("Memory Allocation & Hardware VRAM"))
        vitals_grid = QHBoxLayout()
        vitals_grid.setSpacing(12)

        # RAM Breakdown Card
        self.ram_group = QFrame()
        self.ram_group.setProperty("card", "true")
        rc_lay = QVBoxLayout(self.ram_group)
        rc_lay.setContentsMargins(14, 12, 14, 12)
        rc_lay.setSpacing(8)
        rc_head = QLabel("Physical RAM (4-Metric)")
        rc_head.setProperty("strong", "true")
        rc_lay.addWidget(rc_head)

        metrics_grid = QGridLayout()
        metrics_grid.setSpacing(8)
        self.ram_total_card, self.ram_total_value, _ = stat_card("Total", "--", "", self._theme)
        self.ram_used_card, self.ram_used_value, _ = stat_card("In Use", "--", "", self._theme)
        self.ram_free_card, self.ram_free_value, _ = stat_card("Available", "--", "", self._theme)
        self.ram_cached_card, self.ram_cached_value, _ = stat_card(
            "Cached / Standby", "--", "", self._theme
        )
        metrics_grid.addWidget(self.ram_total_card, 0, 0)
        metrics_grid.addWidget(self.ram_used_card, 0, 1)
        metrics_grid.addWidget(self.ram_free_card, 1, 0)
        metrics_grid.addWidget(self.ram_cached_card, 1, 1)
        rc_lay.addLayout(metrics_grid)
        vitals_grid.addWidget(self.ram_group, 5)

        # Side Column for Swap & GPU VRAM
        side_col = QVBoxLayout()
        side_col.setSpacing(10)

        # Swap Card
        self.swap_group = QFrame()
        self.swap_group.setProperty("card", "true")
        sc_lay = QVBoxLayout(self.swap_group)
        sc_lay.setContentsMargins(14, 12, 14, 12)
        sc_lay.setSpacing(6)
        sc_top = QHBoxLayout()
        sc_title = QLabel("Swap / Pagefile")
        sc_title.setProperty("subtle", "true")
        sc_top.addWidget(sc_title)
        sc_top.addStretch(1)
        self.swap_badge = badge("--", "accent")
        sc_top.addWidget(self.swap_badge)
        sc_lay.addLayout(sc_top)

        self.swap_bar = QProgressBar()
        self.swap_bar.setRange(0, 100)
        self.swap_bar.setValue(0)
        self.swap_bar.setFixedHeight(5)
        self.swap_bar.setTextVisible(False)
        sc_lay.addWidget(self.swap_bar)

        self.swap_label = QLabel("--")
        self.swap_label.setProperty("subtle", "true")
        self.swap_label.setStyleSheet(f"font-size: 10px; color: {_c(self._theme, 'muted')};")
        sc_lay.addWidget(self.swap_label)
        side_col.addWidget(self.swap_group)

        # GPU VRAM Card
        self.gpu_group = QFrame()
        self.gpu_group.setProperty("card", "true")
        self.gpu_layout = QVBoxLayout(self.gpu_group)
        self.gpu_layout.setContentsMargins(14, 12, 14, 12)
        self.gpu_layout.setSpacing(6)

        gpu_placeholder = QLabel("Reading graphics adapters...")
        gpu_placeholder.setProperty("subtle", "true")
        gpu_placeholder.setWordWrap(True)
        self.gpu_layout.addWidget(gpu_placeholder)
        side_col.addWidget(self.gpu_group)

        vitals_grid.addLayout(side_col, 4)
        layout.addLayout(vitals_grid)

        # 3. Reclamation Actions Section
        layout.addWidget(section_label("Reclamation & Optimization Actions"))
        actions_grid = QGridLayout()
        actions_grid.setSpacing(10)

        row_idx = 0
        for action in available_memory_actions():
            card = self._create_action_card(action)
            r, c = divmod(row_idx, 2)
            actions_grid.addWidget(card, r, c)
            row_idx += 1

        layout.addLayout(actions_grid)
        layout.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

    def _create_action_card(self, action) -> QFrame:
        card = QFrame()
        card.setProperty("card", "true")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)

        top = QHBoxLayout()
        title = QLabel(action.name)
        title.setProperty("strong", "true")
        top.addWidget(title)
        top.addStretch(1)

        if action.requires_admin:
            top.addWidget(badge("ADMIN", "warn" if not is_admin() else "safe"))
        elif action.id in ("flush_all", "process_working_sets"):
            top.addWidget(badge("RECOMMENDED", "accent"))
        elif action.kind == "vram":
            top.addWidget(badge("DIAGNOSTIC", "muted"))
        lay.addLayout(top)

        desc = QLabel(action.description)
        desc.setWordWrap(True)
        desc.setProperty("subtle", "true")
        desc.setStyleSheet(f"font-size: 11px; color: {_c(self._theme, 'muted')};")
        lay.addWidget(desc)

        effect = QLabel(action.effect)
        effect.setWordWrap(True)
        effect.setStyleSheet(f"font-size: 10px; color: {_c(self._theme, 'faint')};")
        lay.addWidget(effect)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn = QPushButton("Inspect" if action.kind == "vram" else "Run Action")
        if action.id in ("flush_all", "process_working_sets"):
            btn.setProperty("primary", "true")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda _=False, a=action.id: self._run_action(a))
        if not action.supported:
            btn.setEnabled(False)
            btn.setToolTip(action.unsupported_reason)
        btn_row.addWidget(btn)
        lay.addLayout(btn_row)

        self._action_rows[action.id] = effect
        self._action_cards[action.id] = (card, desc, effect, btn)
        return card

    def refresh(self):
        if self._busy:
            return
        self._busy = True
        self.refresh_btn.setEnabled(False)
        if hasattr(self, "flush_btn"):
            self.flush_btn.setEnabled(False)
        self.status_label.setText("Reading memory statistics...")
        from crapcleaner.gui.workers import MemoryReportWorker, stop_worker

        stop_worker(getattr(self, "_report_worker", None))

        worker = MemoryReportWorker(parent=self)
        self._report_worker = worker
        worker.done.connect(self._on_report)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(
            lambda: (
                setattr(self, "_report_worker", None)
                if getattr(self, "_report_worker", None) is worker
                else None
            )
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_failed(self, message: str):
        self._busy = False
        self.refresh_btn.setEnabled(True)
        if hasattr(self, "flush_btn"):
            self.flush_btn.setEnabled(True)
        self.status_label.setText(f"Could not read memory statistics: {message}")

    def _on_report(self, report):
        self._busy = False
        self.refresh_btn.setEnabled(True)
        if hasattr(self, "flush_btn"):
            self.flush_btn.setEnabled(True)
        self._report = report
        ram = report.ram

        pct = int(ram.percent_used)
        self.hero_title.setText(
            f"{format_size(ram.used_bytes)} / {format_size(ram.total_bytes)} ({pct}% in use)"
        )
        self.ram_bar.setValue(pct)
        self.ram_bar.setProperty("good", ram.percent_used < 70)
        self.ram_bar.setProperty("warn", 70 <= ram.percent_used <= 90)
        self.ram_bar.setProperty("bad", ram.percent_used > 90)
        self.ram_bar.style().unpolish(self.ram_bar)
        self.ram_bar.style().polish(self.ram_bar)

        self.hero_badge.setText(f"{ram.pressure.upper()} PRESSURE")
        self.hero_badge.setProperty(
            "level",
            (
                "safe"
                if ram.pressure in ("low", "normal")
                else ("warn" if ram.pressure == "high" else "danger")
            ),
        )
        self.hero_badge.style().unpolish(self.hero_badge)
        self.hero_badge.style().polish(self.hero_badge)

        self.status_label.setText(
            f"{format_size(ram.available_bytes)} available of {format_size(ram.total_bytes)}"
        )
        self.pressure_label.setText(
            f"Memory pressure: {ram.pressure}"
            + (
                ""
                if ram.cached_known
                else "  -  cached/standby memory is not reported on this platform"
            )
        )

        self.ram_total_value.setText(format_size(ram.total_bytes))
        self.ram_used_value.setText(format_size(ram.used_bytes))
        self.ram_free_value.setText(format_size(ram.available_bytes))
        self.ram_cached_value.setText(
            format_size(ram.cached_bytes) if ram.cached_known else "unknown"
        )

        if ram.swap_supported:
            swap_pct = (
                int(round(ram.swap_used_bytes / ram.swap_total_bytes * 100))
                if ram.swap_total_bytes > 0
                else 0
            )
            self.swap_bar.setValue(swap_pct)
            self.swap_badge.setText(f"{swap_pct}% Used")
            self.swap_label.setText(
                f"{format_size(ram.swap_used_bytes)} used of {format_size(ram.swap_total_bytes)}"
            )
        else:
            self.swap_bar.setValue(0)
            self.swap_badge.setText("Disabled")
            self.swap_label.setText("No swap or pagefile is configured on this system.")

        self._populate_gpus(report)

    def _populate_gpus(self, report):
        while self.gpu_layout.count():
            item = self.gpu_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

        if not report.gpus:
            empty = QLabel("No graphics adapter with readable memory counters was detected.")
            empty.setProperty("subtle", "true")
            empty.setWordWrap(True)
            self.gpu_layout.addWidget(empty)
            return

        for gpu in report.gpus:
            holder = QWidget()
            box = QVBoxLayout(holder)
            box.setContentsMargins(0, 0, 0, 0)
            box.setSpacing(4)
            vendor = f" ({gpu.vendor})" if gpu.vendor else ""
            title = QLabel(f"<b>{gpu.name}</b>{vendor}")
            title.setWordWrap(True)
            box.addWidget(title)

            if gpu.live_usage_available:
                bar = QProgressBar()
                bar.setRange(0, 100)
                bar.setValue(int(gpu.percent_used))
                bar.setFixedHeight(5)
                bar.setTextVisible(False)
                box.addWidget(bar)
                detail = QLabel(
                    f"{format_size(gpu.used_bytes)} used of {format_size(gpu.total_bytes)}, "
                    f"{format_size(gpu.free_bytes)} free (source: {gpu.source})"
                )
            elif gpu.total_bytes:
                detail = QLabel(
                    f"{format_size(gpu.total_bytes)} of VRAM installed. This driver exposes no "
                    "live usage counter, so used and free memory are unknown rather than zero."
                )
            else:
                detail = QLabel("This adapter does not report its memory capacity.")
            detail.setProperty("subtle", "true")
            detail.setStyleSheet(f"font-size: 10px; color: {_c(self._theme, 'muted')};")
            detail.setWordWrap(True)
            box.addWidget(detail)
            self.gpu_layout.addWidget(holder)

        if report.vram_consumers:
            consumers = QLabel(
                "Processes holding VRAM: "
                + ", ".join(
                    f"{c.name} (PID {c.pid}, {format_size(c.used_bytes)})"
                    for c in report.vram_consumers[:8]
                )
            )
            consumers.setWordWrap(True)
            consumers.setProperty("subtle", "true")
            consumers.setStyleSheet(f"font-size: 10px; color: {_c(self._theme, 'muted')};")
            self.gpu_layout.addWidget(consumers)

    def _run_action(self, action_id: str):
        if self._busy:
            return
        action = get_memory_action(action_id)
        if action is None:
            return
        if action.requires_admin and not is_admin():
            QMessageBox.information(
                self,
                action.name,
                f"{action.name} needs administrator privileges.\n\n"
                "Restart CrapCleaner elevated to use this action.",
            )
            return
        if action.kind != "vram" and action.requires_admin:
            confirm = QMessageBox.question(
                self,
                action.name,
                f"{action.description}\n\nWhat runs:\n{action.effect}\n\nContinue?",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        self._busy = True
        self.refresh_btn.setEnabled(False)
        if hasattr(self, "flush_btn"):
            self.flush_btn.setEnabled(False)
        self.result_label.setText(f"Running: {action.name}...")
        self.result_banner.setVisible(True)
        from crapcleaner.gui.workers import MemoryActionWorker, stop_worker

        stop_worker(getattr(self, "_action_worker", None))

        worker = MemoryActionWorker(action_id, parent=self)
        self._action_worker = worker
        worker.done.connect(self._on_action_done)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(
            lambda: (
                setattr(self, "_action_worker", None)
                if getattr(self, "_action_worker", None) is worker
                else None
            )
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def closeEvent(self, event):
        from crapcleaner.gui.workers import stop_worker

        stop_worker(getattr(self, "_report_worker", None))
        stop_worker(getattr(self, "_action_worker", None))
        super().closeEvent(event)

    def _relaunch_admin(self):
        if elevate():
            QApplication.quit()

    def _on_action_done(self, result):
        self._busy = False
        self.refresh_btn.setEnabled(True)
        if hasattr(self, "flush_btn"):
            self.flush_btn.setEnabled(True)
        if not result.success:
            self.result_label.setText(f"Not performed: {result.message}")
            self.result_icon.setPixmap(
                material_icon("warning", _c(self._theme, "warning")).pixmap(18, 18)
            )
            self.result_banner.setVisible(True)
            return
        if not result.measurable:
            self.result_label.setText(result.message)
            self.result_icon.setPixmap(
                material_icon("info", _c(self._theme, "accent")).pixmap(18, 18)
            )
            self.result_banner.setVisible(True)
            return
        before = format_size(result.before.available_bytes)
        after = format_size(result.after.available_bytes)
        delta = result.available_delta_bytes
        change = f"{'+' if delta >= 0 else '-'}{format_size(abs(delta))}"
        extra_tip = ""
        if (
            not is_admin()
            and is_windows()
            and self._report
            and getattr(self._report.ram, "cached_bytes", 0) > 500 * 1024**2
        ):
            cached_str = format_size(self._report.ram.cached_bytes)
            extra_tip = (
                f" (Tip: Relaunch as Administrator to also purge {cached_str} of Standby Cache)."
            )
        self.result_label.setText(
            f"{result.message} Available memory went from {before} to {after} ({change} "
            f"system-wide, including everything else running).{extra_tip}"
        )
        self.result_icon.setPixmap(material_icon("check", _c(self._theme, "safe")).pixmap(18, 18))
        self.result_banner.setVisible(True)
        self.refresh()

    def apply_theme(self, theme: str):
        self._theme = theme
        self.hero_title.setStyleSheet(
            f"font-size: 24px; font-weight: 800; color: {_c(theme, 'text')};"
        )
        self.status_label.setStyleSheet(f"font-size: 11px; color: {_c(theme, 'muted')};")
        self.pressure_label.setStyleSheet(f"font-size: 11px; color: {_c(theme, 'muted')};")
        self.result_label.setStyleSheet(f"font-weight: 600; color: {_c(theme, 'text')};")
        for effect in self._action_rows.values():
            effect.setStyleSheet(f"font-size: 11px; color: {_c(theme, 'faint')};")
