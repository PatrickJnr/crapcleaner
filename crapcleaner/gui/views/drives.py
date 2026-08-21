"""Drive hardware view: per-disk health and per-volume maintenance."""

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
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
from crapcleaner.gui.views.common import _c, badge, section_label
from crapcleaner.system.drive_actions import optimisation_supported
from crapcleaner.utils.format import format_size
from crapcleaner.utils.platform import can_elevate, elevate, is_admin, is_windows

#: Shown wherever a reading exists but this process is not allowed to read it.
_NEEDS_ADMIN = "needs admin"

#: Column widths. The rows repeat down the page, so they are fixed rather than
#: naturally sized: ragged columns are what made the list hard to scan.
_W_DRIVE, _W_BAR, _W_USED, _W_FREE, _W_TRIM, _W_FRAG, _W_BTN = 340, 170, 165, 110, 74, 110, 88
_COL_GAP = 10


def _telemetry(disk: Any) -> list[str]:
    """Only the counters the drive actually gave. An absent one says nothing worth a slot."""
    readings = [
        ("Temp", disk.temperature_c, "°C"),
        ("Wear", disk.wear_percent, "%"),
        ("Powered on", f"{disk.power_on_hours:,}" if disk.power_on_hours else None, "h"),
        ("Read errors", disk.read_errors, ""),
        ("Write errors", disk.write_errors, ""),
    ]
    return [
        f"{name}  {value}{(' ' + suffix) if suffix else ''}"
        for name, value, suffix in readings
        if value is not None
    ]


def _frag_reading(value: int) -> str:
    """Windows measures a percentage; e4defrag reports a 0-100 score, not a percentage."""
    return f"{value}%" if is_windows() else f"score {value}"


def _relaunch_label() -> str:
    return "Relaunch as Admin" if is_windows() else "Relaunch as Root"


def _health_level(status: str) -> str:
    lowered = status.lower()
    if lowered == "healthy":
        return "safe"
    if lowered in ("warning", "unknown"):
        return "warning"
    return "danger"


class DrivesView(QWidget):
    """Physical disks with their volumes, reliability counters, TRIM, and optimisation."""

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main = main_window
        self._theme = "dark"
        self._drives: list = []
        self._schedule = ("Unknown", "")
        #: True until the scheduled-optimisation query has answered once. The inventory
        #: comes from a cache and paints immediately; that query cannot, so the banner
        #: says it is still running rather than reporting "Unknown".
        self._schedule_pending = True
        self._worker = None
        self._action_worker = None
        self._bulk_action = ""
        #: Whether this machine can analyse or optimise a volume at all. A Linux box
        #: without fstrim cannot, and the column, the buttons, and the schedule line are
        #: left out entirely rather than shown as a row of dashes.
        self._optimisation = optimisation_supported()
        #: drive letter -> the label showing its fragmentation reading.
        self._frag_labels: dict[str, QLabel] = {}
        self._build_ui()

    # --- construction ---------------------------------------------------------

    def _build_ui(self):
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(28, 24, 28, 24)
        root_lay.setSpacing(16)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        h1 = QLabel("Drives")
        h1.setObjectName("ViewTitle")
        sub = QLabel(
            "Inspect drive health, temperature, wear, and TRIM, and run Windows' own "
            "drive optimisation."
            if self._optimisation and is_windows()
            else (
                "Inspect drive health, temperature, wear, and TRIM, and run fstrim and "
                "fragmentation checks."
                if self._optimisation
                else "Inspect drive health, temperature, wear, and TRIM support."
            )
        )
        sub.setProperty("subtle", "true")
        titles.addWidget(h1)
        titles.addWidget(sub)
        header.addLayout(titles)
        header.addStretch(1)

        if not is_admin() and can_elevate():
            self.elevate_btn = QPushButton(_relaunch_label())
            self.elevate_btn.setProperty("secondary", "true")
            self.elevate_btn.setIcon(material_icon("security", _c(self._theme, "accent")))
            self.elevate_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.elevate_btn.clicked.connect(self._relaunch_admin)
            header.addWidget(self.elevate_btn)

        self.analyze_all_btn = QPushButton("Analyse All")
        self.analyze_all_btn.setProperty("secondary", "true")
        self.analyze_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.analyze_all_btn.clicked.connect(self._analyze_all)
        header.addWidget(self.analyze_all_btn)

        self.optimize_all_btn = QPushButton("Optimise All")
        self.optimize_all_btn.setProperty("secondary", "true")
        self.optimize_all_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.optimize_all_btn.clicked.connect(self._optimize_all)
        header.addWidget(self.optimize_all_btn)

        self.analyze_all_btn.setVisible(self._optimisation)
        self.optimize_all_btn.setVisible(self._optimisation)

        self.refresh_btn = QPushButton("Refresh Drives")
        self.refresh_btn.setProperty("primary", "true")
        self.refresh_btn.setIcon(material_icon("refresh", "#ffffff"))
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(lambda: self.refresh_drives(force=True))
        header.addWidget(self.refresh_btn)

        root_lay.addLayout(header)

        self.status_card = QFrame()
        self.status_card.setProperty("card", "true")
        status_lay = QVBoxLayout(self.status_card)
        status_lay.setContentsMargins(16, 12, 16, 12)
        status_lay.setSpacing(4)
        self.status_label = QLabel("Reading drive information...")
        self.status_label.setWordWrap(True)
        status_lay.addWidget(self.status_label)
        # The caveats are true of the whole machine, not of each drive, so they belong
        # here once instead of repeated under every row.
        self.notes_label = QLabel("")
        self.notes_label.setWordWrap(True)
        self.notes_label.setVisible(False)
        status_lay.addWidget(self.notes_label)
        root_lay.addWidget(self.status_card)

        table = QFrame()
        table.setProperty("card", "true")
        table_lay = QVBoxLayout(table)
        table_lay.setContentsMargins(18, 14, 18, 14)
        table_lay.setSpacing(0)

        self._column_header = self._header_row()
        table_lay.addWidget(self._column_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._cards_host = QWidget()
        self._cards_lay = QVBoxLayout(self._cards_host)
        self._cards_lay.setContentsMargins(0, 0, 0, 0)
        self._cards_lay.setSpacing(0)
        self._cards_lay.addStretch(1)
        scroll.setWidget(self._cards_host)
        table_lay.addWidget(scroll, 1)

        root_lay.addWidget(table, 1)

        self._update_bulk_enabled()

    def _header_row(self) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 8)
        lay.setSpacing(_COL_GAP)

        right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        for text, width, stretch, align in (
            ("DRIVE", _W_DRIVE, 0, Qt.AlignmentFlag.AlignLeft),
            ("", _W_BAR, 0, Qt.AlignmentFlag.AlignLeft),
            ("USED", _W_USED, 0, Qt.AlignmentFlag.AlignLeft),
            ("FREE", _W_FREE, 0, Qt.AlignmentFlag.AlignLeft),
            ("TRIM", _W_TRIM, 0, Qt.AlignmentFlag.AlignCenter),
        ) + (
            (
                ("FRAG", _W_FRAG, 0, right),
                ("", _W_BTN * 2 + _COL_GAP, 0, Qt.AlignmentFlag.AlignLeft),
            )
            if self._optimisation
            else ()
        ):
            label = section_label(text)
            label.setAlignment(align)
            if stretch:
                label.setMinimumWidth(width)
            else:
                label.setFixedWidth(width)
            lay.addWidget(label, stretch)
        # Columns are fixed, so the slack goes to the right rather than opening a gap
        # in the middle of every row.
        lay.addStretch(1)
        return row

    # --- data -----------------------------------------------------------------

    def refresh_drives(self, force: bool = False):
        from crapcleaner.gui.workers import DrivesWorker, stop_worker

        # The inventory survives across launches, so the table can be on screen before
        # the worker starts. Only the parts that cannot be cached are waited for.
        if not force and not self._drives:
            from crapcleaner.system.drives import cached_drives_report

            known = cached_drives_report()
            if known:
                self._drives = known
                self._populate()

        stop_worker(getattr(self, "_worker", None))

        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Loading...")

        worker = DrivesWorker(force_refresh=force, parent=self)
        self._worker = worker
        worker.done.connect(self._on_loaded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(
            lambda: (
                setattr(self, "_worker", None) if getattr(self, "_worker", None) is worker else None
            )
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_loaded(self, drives: list, schedule_state: str, schedule_detail: str):
        self._drives = drives
        self._schedule = (schedule_state, schedule_detail)
        self._schedule_pending = False
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Refresh Drives")
        self._populate()

    def _on_failed(self, message: str):
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Refresh Drives")
        self.status_label.setText(f"Could not read drive information: {message}")

    # --- rendering ------------------------------------------------------------

    def _clear_cards(self):
        self._frag_labels.clear()
        while self._cards_lay.count() > 1:
            item = self._cards_lay.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

    def _populate(self):
        self._clear_cards()

        parts = []
        if self._optimisation:
            if self._schedule_pending:
                parts.append("Checking scheduled optimisation...")
            else:
                state, detail = self._schedule
                parts.append(f"Scheduled optimisation: {state}.")
                if detail:
                    parts.append(detail)

        # Virtual and network mounts have no media to inspect or optimise, so they are
        # left out here. Their space is still reported on the Dashboard and in Storage
        # Breakdown, and the count keeps their absence from looking like a bug.
        hidden = sum(len(disk.volumes) for disk in self._drives if disk.is_unmapped)
        if hidden and self._optimisation:
            parts.append(
                f"{hidden} virtual drive{'s' if hidden != 1 else ''} hidden — "
                "they have no media to optimise."
            )
        self.status_label.setText("   ·   ".join(parts))
        self.status_label.setVisible(bool(parts))
        # An empty banner is a box of nothing; it appears only when it has something
        # to say, which on Linux is often neither line.
        has_notes = self._set_notes()
        self.status_card.setVisible(bool(parts) or has_notes)

        disks = [disk for disk in self._drives if not disk.is_unmapped]
        self._column_header.setVisible(bool(disks))

        for disk in disks:
            # One volume is the common case, and a nested block for a single child is
            # structure without information. Only a shared disk earns its own heading.
            shared = len(disk.volumes) > 1
            if shared:
                self._add_row(self._disk_heading(disk))
            for index, volume in enumerate(disk.volumes):
                # No rule between a heading and the first volume under it, or the
                # heading reads as belonging to the disk above.
                self._add_row(
                    self._volume_row(volume, disk, not shared),
                    separated=not (shared and index == 0),
                )

        self._update_bulk_enabled()

    def _add_row(self, widget: QWidget, separated: bool = True):
        if separated and self._cards_lay.count() > 1:
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setFixedHeight(1)
            line.setStyleSheet(f"color: {_c(self._theme, 'border')};")
            self._cards_lay.insertWidget(self._cards_lay.count() - 1, line)
        self._cards_lay.insertWidget(self._cards_lay.count() - 1, widget)

    def _set_notes(self) -> bool:
        """Caveats that apply to the machine, said once rather than per drive."""
        notes = []
        if not is_admin() and (is_windows() or self._optimisation):
            notes.append(
                f"Reliability counters unavailable — {_NEEDS_ADMIN}. Temperature, wear, "
                "and drive optimisation need an elevated session."
            )
        else:
            silent = [d for d in self._drives if not d.is_unmapped and not _telemetry(d)]
            if len(silent) > 2:
                # Listing every model is a wall of text that says the same thing as a count.
                notes.append(f"{len(silent)} drives do not report reliability counters.")
            elif silent:
                names = ", ".join(d.model for d in silent)
                verb = "does" if len(silent) == 1 else "do"
                notes.append(f"{names} {verb} not report reliability counters.")

        self.notes_label.setText(" ".join(notes))
        self.notes_label.setVisible(bool(notes))
        self.notes_label.setStyleSheet(f"color: {_c(self._theme, 'muted')}; font-size: 11px;")
        return bool(notes)

    def _disk_heading(self, disk: Any) -> QWidget:
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 10, 0, 2)
        lay.setSpacing(8)
        lay.addWidget(self._detail_label(disk, bold=True))
        lay.addStretch(1)
        if _health_level(disk.health_status) != "safe":
            lay.addWidget(badge(disk.health_status.upper(), _health_level(disk.health_status)))
        return row

    def _detail_label(self, disk: Any, bold: bool = False) -> QLabel:
        """Model, media, and whatever counters the drive actually gave, on one line."""
        bits = [disk.model, disk.media_type]
        if disk.bus_type and disk.bus_type != "Unknown":
            bits.append(disk.bus_type)
        bits += _telemetry(disk)

        label = QLabel(" · ".join(b for b in bits if b))
        weight = "600" if bold else "400"
        label.setStyleSheet(
            f"color: {_c(self._theme, 'muted')}; font-size: 11px; font-weight: {weight};"
        )
        return label

    def _volume_row(self, volume: Any, disk: Any, show_disk: bool) -> QFrame:
        row = QFrame()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 9, 0, 9)
        lay.setSpacing(_COL_GAP)

        name_col = QVBoxLayout()
        name_col.setContentsMargins(0, 0, 0, 0)
        name_col.setSpacing(2)

        name = volume.letter + (f"  {volume.label}" if volume.label else "")
        if volume.filesystem:
            name += f"  ·  {volume.filesystem}"
        letter_lbl = QLabel(name)
        letter_lbl.setStyleSheet(
            f"font-weight: 600; font-size: 13px; color: {_c(self._theme, 'text')}"
        )
        name_col.addWidget(letter_lbl)
        # A disk with one volume needs no heading of its own, so the drive it lives on is
        # named right here instead.
        if show_disk:
            name_col.addWidget(self._detail_label(disk))

        name_host = QWidget()
        name_host.setLayout(name_col)
        name_host.setFixedWidth(_W_DRIVE)
        lay.addWidget(name_host)

        lay.addWidget(self._usage_bar(volume))

        used = max(volume.capacity - volume.free_space, 0)
        used_lbl = QLabel(f"{format_size(used)} of {format_size(volume.capacity)}")
        used_lbl.setStyleSheet(f"color: {_c(self._theme, 'text')}")
        used_lbl.setFixedWidth(_W_USED)
        lay.addWidget(used_lbl)

        free_lbl = QLabel(f"{format_size(volume.free_space)} free")
        free_lbl.setStyleSheet(f"color: {_c(self._theme, 'muted')}")
        free_lbl.setFixedWidth(_W_FREE)
        lay.addWidget(free_lbl)

        trim_text = "On" if volume.trim_enabled else ("Off" if volume.trim_supported else "—")
        trim_badge = badge(trim_text, "safe" if volume.trim_enabled else "muted")
        trim_badge.setFixedWidth(_W_TRIM)
        trim_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(trim_badge)

        if not self._optimisation:
            lay.addStretch(1)
            return row

        frag_lbl = QLabel(self._fragmentation_text(volume))
        frag_lbl.setStyleSheet(f"color: {_c(self._theme, 'muted')}")
        frag_lbl.setFixedWidth(_W_FRAG)
        frag_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._frag_labels[volume.letter] = frag_lbl
        lay.addWidget(frag_lbl)

        elevated = is_admin() and self._optimisation
        tooltip = "" if elevated else f"{_relaunch_label()} to use this."

        analyze_btn = QPushButton("Analyse")
        analyze_btn.setProperty("secondary", "true")
        analyze_btn.setFixedWidth(_W_BTN)
        analyze_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        analyze_btn.setEnabled(elevated)
        analyze_btn.setToolTip(tooltip)
        analyze_btn.clicked.connect(lambda _=False, v=volume: self._analyze(v))
        lay.addWidget(analyze_btn)

        optimize_btn = QPushButton("Optimise")
        optimize_btn.setProperty("secondary", "true")
        optimize_btn.setFixedWidth(_W_BTN)
        optimize_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        optimize_btn.setEnabled(elevated)
        optimize_btn.setToolTip(tooltip)
        optimize_btn.clicked.connect(lambda _=False, v=volume: self._optimize(v))
        lay.addWidget(optimize_btn)
        lay.addStretch(1)

        return row

    def _usage_bar(self, volume: Any) -> QProgressBar:
        """How full the volume is, which is the one number worth seeing at a glance."""
        percent = (
            int((volume.capacity - volume.free_space) / volume.capacity * 100)
            if volume.capacity
            else 0
        )

        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(percent)
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        bar.setFixedWidth(_W_BAR)
        bar.setProperty("good", percent < 70)
        bar.setProperty("warn", 70 <= percent <= 85)
        bar.setProperty("bad", percent > 85)
        bar.setToolTip(f"{percent}% full")
        return bar

    def _fragmentation_text(self, volume: Any) -> str:
        if volume.fragmentation_percent is None:
            return volume.defrag_verdict or "—"
        return _frag_reading(volume.fragmentation_percent)

    # --- actions --------------------------------------------------------------

    def _analyze(self, volume: Any):
        from crapcleaner.gui.workers import DriveAnalyzeWorker, stop_worker

        stop_worker(getattr(self, "_action_worker", None))

        label = self._frag_labels.get(volume.letter)
        if label is not None:
            label.setText("Analysing...")

        worker = DriveAnalyzeWorker(volume.letter, parent=self)
        self._action_worker = worker
        worker.done.connect(self._on_analyzed)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_analyzed(self, letter: str, ok: bool, message: str, percent):
        for disk in self._drives:
            for volume in disk.volumes:
                if volume.letter != letter:
                    continue
                volume.fragmentation_percent = percent if ok else None
                volume.defrag_verdict = message if ok else None

        label = self._frag_labels.get(letter)
        if label is not None:
            label.setText(_frag_reading(percent) if ok and percent is not None else "—")
        self.status_label.setText(message)

    def _optimize(self, volume: Any):
        answer = QMessageBox.question(
            self,
            "Optimise Drive",
            f"Optimise {volume.letter} ({format_size(volume.capacity)})?\n\n"
            + (
                "Windows will retrim a solid-state drive or defragment a hard disk. "
                "On a large hard disk this can run for hours.\n\n"
                if is_windows()
                else "fstrim will discard the unused blocks on this volume.\n\n"
            )
            + "You can keep using the machine while it runs.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        from crapcleaner.gui.workers import DriveOptimizeWorker, stop_worker

        stop_worker(getattr(self, "_action_worker", None))
        self.status_label.setText(f"Optimising {volume.letter}... this can take a long time.")

        worker = DriveOptimizeWorker(volume.letter, parent=self)
        self._action_worker = worker
        worker.done.connect(self._on_optimized)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_optimized(self, letter: str, ok: bool, message: str):
        self.status_label.setText(message)
        if ok:
            self.refresh_drives(force=True)

    # --- bulk actions ---------------------------------------------------------

    def _optimisable_volumes(self) -> list[Any]:
        """Volumes Windows can actually optimise.

        The unmapped group holds virtual and network mounts such as a cloud drive; there
        is no physical media behind them to trim or defragment.
        """
        return [v for disk in self._drives if not disk.is_unmapped for v in disk.volumes]

    def _update_bulk_enabled(self):
        """A sweep needs both the rights to run and an inventory to run against."""
        elevated = is_admin() and self._optimisation
        targets = self._optimisable_volumes()

        if not elevated:
            tooltip = f"{_relaunch_label()} to use this."
        elif not targets:
            tooltip = "No drives loaded yet."
        else:
            tooltip = ""

        for button in (self.analyze_all_btn, self.optimize_all_btn):
            button.setEnabled(bool(elevated and targets))
            button.setToolTip(tooltip)

    def _analyze_all(self):
        volumes = self._optimisable_volumes()
        if not volumes:
            self.status_label.setText("No drives available to analyse.")
            return
        self._start_bulk("analyze", volumes)

    def _optimize_all(self):
        volumes = self._optimisable_volumes()
        if not volumes:
            self.status_label.setText("No drives available to optimise.")
            return

        total_size = format_size(sum(v.capacity for v in volumes))
        letters = ", ".join(v.letter for v in volumes)
        answer = QMessageBox.question(
            self,
            "Optimise All Drives",
            f"Optimise {len(volumes)} drives ({letters}), {total_size} in total?\n\n"
            + (
                "Windows will retrim each solid-state drive and defragment each hard disk, "
                "one at a time. Across drives this size it can run for many hours.\n\n"
                if is_windows()
                else "fstrim will discard the unused blocks on each volume, one at a time.\n\n"
            )
            + "You can stop between drives, but a drive already being optimised will "
            "finish first.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._start_bulk("optimize", volumes)

    def _start_bulk(self, action: str, volumes: list[Any]):
        from crapcleaner.gui.workers import DriveBulkWorker, stop_worker

        stop_worker(getattr(self, "_action_worker", None))

        if action == "analyze":
            for volume in volumes:
                label = self._frag_labels.get(volume.letter)
                if label is not None:
                    label.setText("Queued...")

        worker = DriveBulkWorker([v.letter for v in volumes], action, parent=self)
        self._action_worker = worker
        worker.started_volume.connect(self._on_bulk_started)
        worker.progress.connect(self._on_bulk_progress)
        worker.done.connect(self._on_bulk_done)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(worker.deleteLater)

        self._set_bulk_running(action, True)
        worker.start()

    def _set_bulk_running(self, action: str, running: bool):
        """While a sweep runs, its own button becomes the way to stop it."""
        button = self.analyze_all_btn if action == "analyze" else self.optimize_all_btn
        other = self.optimize_all_btn if action == "analyze" else self.analyze_all_btn
        default = "Analyse All" if action == "analyze" else "Optimise All"

        button.setText("Stop" if running else default)
        try:
            button.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        button.clicked.connect(
            self._stop_bulk
            if running
            else (self._analyze_all if action == "analyze" else self._optimize_all)
        )
        self.refresh_btn.setEnabled(not running)
        self._bulk_action = action if running else ""

        if running:
            other.setEnabled(False)
        else:
            self._update_bulk_enabled()

    def _stop_bulk(self):
        worker = getattr(self, "_action_worker", None)
        if worker is not None:
            worker.request_stop()
        self.status_label.setText("Stopping after the current drive finishes...")

    def _on_bulk_started(self, letter: str, index: int, total: int):
        verb = "Analysing" if self._bulk_action == "analyze" else "Optimising"
        self.status_label.setText(f"{verb} {letter} ({index} of {total})...")
        label = self._frag_labels.get(letter)
        if label is not None and self._bulk_action == "analyze":
            label.setText("Analysing...")

    def _on_bulk_progress(self, letter: str, ok: bool, message: str, percent):
        if self._bulk_action == "analyze":
            self._on_analyzed(letter, ok, message, percent)

    def _on_bulk_done(self, succeeded: int, attempted: int):
        action = self._bulk_action
        self._set_bulk_running(action, False)
        verb = "analysed" if action == "analyze" else "optimised"
        self.status_label.setText(f"{succeeded} of {attempted} drives {verb} successfully.")
        if action == "optimize" and succeeded:
            self.refresh_drives(force=True)

    def _relaunch_admin(self):
        if elevate():
            QApplication.quit()

    # --- lifecycle ------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        if not self._drives:
            self.refresh_drives()

    def apply_theme(self, theme: str):
        self._theme = theme
        if self._drives:
            self._populate()
