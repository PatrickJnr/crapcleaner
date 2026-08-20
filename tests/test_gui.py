"""GUI smoke tests - run offscreen so they work on headless CI too."""

import os
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPalette, qAlpha
from PySide6.QtWidgets import QApplication

from crapcleaner.config import load_settings, update_settings
from crapcleaner.gui import icons
from crapcleaner.gui.app import MainWindow
from crapcleaner.gui.icons import font_available, material_code
from crapcleaner.gui.sidebar import NAV_ITEMS
from crapcleaner.gui.theme import THEMES, apply_theme, palette_for
from crapcleaner.models.category import SafetyLevel
from crapcleaner.models.report import ScanCategoryResult, ScanReport


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


def test_apply_theme_all_palettes(app):
    for theme in THEMES:
        apply_theme(app, theme)
        palette = palette_for(theme)
        assert app.palette().color(QPalette.ColorRole.Window) == QColor(palette["window"])
        assert app.palette().color(QPalette.ColorRole.Highlight) == QColor(palette["accent"])
        assert palette["surface"] in app.styleSheet()


def test_main_window_boots_and_navigates(app):
    apply_theme(app, "dark")
    window = MainWindow()
    window.show()
    for key in window._PAGE_KEYS:
        window.navigate(key)
        assert window.stack.currentIndex() == window._PAGE_KEYS.index(key)
    window.review_and_clean()
    assert window.stack.currentIndex() == window._PAGE_KEYS.index("cleanup")
    window.close()


def test_settings_apply_theme_roundtrip(app):
    window = MainWindow()
    window.show()
    for theme in ("light", "nord", "dark"):
        update_settings(theme=theme)
        window.apply_settings()
        assert window._theme == theme
        assert window._settings["theme"] == theme
        assert load_settings()["theme"] == theme
    window.close()


def test_material_font_loaded():
    assert font_available(), "Material Icons font should load from bundled assets"


@pytest.mark.parametrize("name", [icon_name for _, _, icon_name in NAV_ITEMS] + ["brand"])
def test_icon_names_resolve_to_material_glyphs(name):
    assert len(material_code(name)) == 1, f"{name!r} should map to a single codepoint"


@pytest.mark.parametrize("name", [icon_name for _, _, icon_name in NAV_ITEMS] + ["brand"])
def test_icons_render_non_blank(app, name):
    pm = icons._pix(icons._LOGICAL_SIZE * icons._DEVICE_SCALE)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
    icons.draw_glyph(
        painter,
        QRectF(0, 0, icons._LOGICAL_SIZE, icons._LOGICAL_SIZE),
        name,
        "#ffffff",
        icons._LOGICAL_SIZE,
    )
    painter.end()
    image = pm.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    min_x, min_y, max_x, max_y = image.width(), image.height(), -1, -1
    for y in range(image.height()):
        for x in range(image.width()):
            if qAlpha(image.pixel(x, y)) > 0:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    assert max_x >= 0, f"icon {name!r} rendered blank"
    assert min_x > 0 and min_y > 0 and max_x < image.width() - 1 and max_y < image.height() - 1, (
        f"icon {name!r} is clipped ({min_x},{min_y})-({max_x},{max_y}) in "
        f"{image.width()}x{image.height()}"
    )


def test_cleanup_view_filtering_and_selection(app):
    window = MainWindow()
    view = window.cleanup_view

    view._select_all(True)
    sel = view.selected_categories()
    assert len(sel) > 0

    view._select_all(False)
    assert len(view.selected_categories()) == 0

    view._select_by_safety(True)
    safe_sel = view.selected_categories()
    for cat in safe_sel:
        assert cat.safety_level in (SafetyLevel.SAFE, SafetyLevel.LOW_RISK)

    checkable_categories = [c for c in view._categories if c.safety_level != SafetyLevel.DANGEROUS]
    view._invert_selection()
    inv_sel = view.selected_categories()
    assert len(inv_sel) == len(checkable_categories) - len(safe_sel)

    view._set_safety_filter("SAFE")
    view._set_safety_filter("ALL")

    view.search_edit.setText("python")
    view.search_edit.setText("")

    view.tree_expand_all()
    view.tree_collapse_all()
    window.close()


def test_scan_and_sidebar_badge_updates(app):
    window = MainWindow()
    sample_report = ScanReport(
        started=datetime.now(),
        duration=1.5,
        results=[
            ScanCategoryResult(
                category_id="test_cat",
                name="Test Cache",
                size=104857600,
                item_count=100,
                skipped=0,
                safety_level="SAFE",
                group="Windows",
                description="Test Description",
                reclaimable=True,
            )
        ],
    )
    window._on_scan_done(sample_report)
    assert "(" in window.sidebar._buttons["cleanup"].text()

    window.cancel_active_scan()
    window.close()


def test_large_files_and_duplicates_views(app):
    window = MainWindow()

    lf = window.large_files_view

    class DummyFile:
        name = "test.iso"
        size = 1073741824
        file_type = "iso"
        last_modified = datetime.now()
        path = "C:\\test.iso"

    lf.show_files([DummyFile()])
    assert lf.table.rowCount() == 1
    lf._filter_table("iso")
    assert not lf.table.isRowHidden(0)
    lf._filter_table("nonexistent")
    assert lf.table.isRowHidden(0)

    dp = window.duplicates_view

    class DummyGroup:
        size = 52428800
        duplicate_count = 2
        reclaimable = 52428800
        files = ["C:\\path1.bin", "C:\\path2.bin"]

    dp.show_groups([DummyGroup()])
    assert dp.table.rowCount() == 1

    many_files = [f"C:\\path{i}.bin" for i in range(30)]

    class VerboseGroup:
        size = 1048576
        duplicate_count = len(many_files) - 1
        reclaimable = (len(many_files) - 1) * size
        files = many_files

    dp.show_groups([VerboseGroup() for _ in range(200)])
    assert dp.table.rowCount() <= 150
    tooltip_item = dp.table.item(0, 3)
    assert tooltip_item is not None
    assert "... and" in tooltip_item.toolTip()

    window.close()
