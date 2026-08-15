"""GUI state transitions for the Memory Cleaner view."""

import pytest

from crapcleaner.memory.report import GpuMemoryStats, MemoryReport, MemoryStats


@pytest.fixture
def memory_view():
    from PySide6.QtWidgets import QApplication

    from crapcleaner.gui.views import MemoryView

    QApplication.instance() or QApplication([])

    class DummyMain:
        pass

    return MemoryView(DummyMain())


def _report(**overrides) -> MemoryReport:
    ram = MemoryStats(
        total_bytes=16 * 1024**3,
        available_bytes=8 * 1024**3,
        used_bytes=8 * 1024**3,
        percent_used=50.0,
        swap_total_bytes=4 * 1024**3,
        swap_used_bytes=1 * 1024**3,
        swap_available_bytes=3 * 1024**3,
        swap_supported=True,
    )
    report = MemoryReport(ram=ram)
    for key, value in overrides.items():
        setattr(report, key, value)
    return report


def test_loading_state(memory_view):
    assert "Reading memory" in memory_view.status_label.text()


def test_populated_state(memory_view):
    memory_view._on_report(_report())
    assert memory_view.ram_bar.value() == 50
    assert memory_view.ram_total_value.text().startswith("16")
    assert "available of" in memory_view.status_label.text()
    assert memory_view.swap_bar.value() == 25
    assert memory_view.refresh_btn.isEnabled()


def test_missing_swap_is_explained(memory_view):
    report = _report()
    report.ram.swap_supported = False
    memory_view._on_report(report)
    assert "No swap" in memory_view.swap_label.text()


def test_empty_gpu_state(memory_view):
    memory_view._on_report(_report())
    texts = _labels(memory_view.gpu_layout)
    assert any("No graphics adapter" in t for t in texts)


def test_gpu_without_live_counters_is_not_shown_as_zero(memory_view):
    gpu = GpuMemoryStats(name="Test GPU", vendor="AMD", total_bytes=8 * 1024**3)
    memory_view._on_report(_report(gpus=[gpu]))
    texts = " ".join(_labels(memory_view.gpu_layout))
    assert "unknown rather than zero" in texts


def test_error_state(memory_view):
    memory_view._on_failed("driver exploded")
    assert "driver exploded" in memory_view.status_label.text()
    assert memory_view.refresh_btn.isEnabled()


def test_action_failure_is_reported(memory_view):
    from crapcleaner.memory.cleaner import MemoryActionResult

    memory_view._on_action_done(
        MemoryActionResult(action_id="standby_list", success=False, message="Needs admin.")
    )
    assert "Not performed" in memory_view.result_label.text()


def test_read_only_action_result_has_no_reclaim_claim(memory_view):
    from crapcleaner.memory.cleaner import MemoryActionResult

    memory_view._on_action_done(
        MemoryActionResult(
            action_id="vram_report", success=True, measurable=False, message="30% of VRAM in use"
        )
    )
    assert memory_view.result_label.text() == "30% of VRAM in use"


def test_theme_switch_restyles_action_rows(memory_view):
    memory_view.apply_theme("light")
    assert memory_view._theme == "light"
    for effect in memory_view._action_rows.values():
        assert "color:" in effect.styleSheet()


def _labels(layout) -> list[str]:
    from PySide6.QtWidgets import QLabel

    texts = []
    for index in range(layout.count()):
        widget = layout.itemAt(index).widget()
        if widget is None:
            continue
        texts.extend(child.text() for child in widget.findChildren(QLabel))
        if isinstance(widget, QLabel):
            texts.append(widget.text())
    return texts
