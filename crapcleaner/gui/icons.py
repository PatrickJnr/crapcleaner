"""Google Material Icons for the CrapCleaner GUI.

Icons are rendered from the bundled Google Material Icons font
(MaterialIcons-Regular.ttf, Apache 2.0 - see assets/LICENSE). Glyphs are drawn
as crisp 2x pixmaps and cached per (name, color).
"""

import logging
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QIcon,
    QPainter,
    QPainterPath,
    QPixmap,
)

_ASSETS = Path(__file__).resolve().parent / "assets"
_FONT_PATH = _ASSETS / "MaterialIcons-Regular.ttf"
_CODEPOINTS_PATH = _ASSETS / "MaterialIcons-Regular.codepoints"

_LOGICAL_SIZE = 18
_DEVICE_SCALE = 2
# Glyphs are rendered slightly smaller than the box so they sit centered
# with padding, matching how Material icons are typically displayed.
_GLYPH_SIZE_FACTOR = 0.8

# Logical names used by the UI, mapped to Google Material icon names.
_MATERIAL_NAMES = {
    "brand": "cleaning_services",
    "trash": "delete",
    "spark": "psychology",
    "stack": "storage",
    "specs": "devices",
    "about": "info",
    "hardware": "hardware",
    "person": "account_circle",
}

_logger = logging.getLogger(__name__)

_font_loaded = False
_font_family: str | None = None
_codepoints: dict[str, str] = {}


def _ensure_font():
    global _font_loaded, _font_family
    if _font_loaded:
        return
    _font_loaded = True
    if _CODEPOINTS_PATH.exists():
        try:
            with _CODEPOINTS_PATH.open(encoding="utf-8") as fh:
                for line in fh:
                    parts = line.split()
                    if len(parts) == 2:
                        _codepoints[parts[0]] = parts[1]
        except OSError:
            pass
    if not _FONT_PATH.exists():
        _logger.error("Material Icons font not found: %s", _FONT_PATH)
        return
    font_id = QFontDatabase.addApplicationFont(str(_FONT_PATH))
    families = QFontDatabase.applicationFontFamilies(font_id)
    if families:
        _font_family = families[0]
    else:
        _logger.error("Could not load Material Icons font from %s", _FONT_PATH)


def material_code(name: str) -> str:
    """Return the Unicode codepoint string for a logical icon name."""
    _ensure_font()
    material = _MATERIAL_NAMES.get(name, name)
    code = _codepoints.get(material)
    if code is None:
        _logger.warning("Material icon '%s' not found, falling back to 'help'.", material)
        code = _codepoints.get("help", "e887")
    return chr(int(code, 16))


def font_available() -> bool:
    _ensure_font()
    return _font_family is not None


def draw_glyph(painter: QPainter, rect: QRectF, name: str, color: str, size: float):
    """Draw a Material icon glyph centered inside ``rect``, never clipped."""
    _ensure_font()
    if _font_family is None:
        painter.setPen(QColor(color))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, name[:1].upper())
        return

    font = QFont(_font_family)
    font.setPixelSize(int(size))
    path = QPainterPath()
    path.addText(0, 0, font, material_code(name))
    ink = path.boundingRect()
    if ink.width() <= 0 or ink.height() <= 0:
        return

    target = QRectF(rect).adjusted(size * 0.08, size * 0.08, -size * 0.08, -size * 0.08)
    fit_scale = min(target.width() / ink.width(), target.height() / ink.height())
    scale = min(fit_scale, _GLYPH_SIZE_FACTOR * size / ink.height())

    painter.save()
    painter.translate(target.center())
    painter.scale(scale, scale)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawPath(path.translated(-ink.center()))
    painter.restore()


def _pix(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    pm.setDevicePixelRatio(_DEVICE_SCALE)
    return pm


@lru_cache(maxsize=128)
def icon(name: str, color: str) -> QIcon:
    """Return a cached themed icon for the given logical name."""
    size = _LOGICAL_SIZE * _DEVICE_SCALE
    pm = _pix(size)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
    draw_glyph(painter, QRectF(0, 0, _LOGICAL_SIZE, _LOGICAL_SIZE), name, color, _LOGICAL_SIZE)
    painter.end()
    return QIcon(pm)
