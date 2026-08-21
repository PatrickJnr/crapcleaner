"""Render the application icon to a PNG.

    python scripts/render_icon.py build/crapcleaner.png [size]

The Linux desktop entry needs a PNG, and the icon is drawn in code rather than stored
as a file. Rendering it here means the packaged icon is always the one the application
actually shows, instead of a copy that quietly falls out of step with it.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def render(destination: str, size: int = 256) -> str:
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen, QPixmap
    from PySide6.QtWidgets import QApplication

    from crapcleaner.gui.icons import draw_glyph

    QApplication.instance() or QApplication([])

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)

    # The same proportions as make_window_icon, which draws at 64.
    scale = size / 64
    rect = QRectF(2 * scale, 2 * scale, 60 * scale, 60 * scale)
    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradient.setColorAt(0.0, QColor("#2563eb"))
    gradient.setColorAt(1.0, QColor("#60a5fa"))
    painter.setBrush(QBrush(gradient))
    painter.setPen(QPen(QColor("#3b82f6"), max(1, round(scale))))
    painter.drawRoundedRect(rect, 14 * scale, 14 * scale)
    draw_glyph(painter, rect, "brand", "#ffffff", round(38 * scale))
    painter.end()

    parent = os.path.dirname(os.path.abspath(destination))
    if parent:
        os.makedirs(parent, exist_ok=True)
    if not pixmap.save(destination, "PNG"):
        raise SystemExit(f"could not write {destination}")
    return destination


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "build/crapcleaner.png"
    px = int(sys.argv[2]) if len(sys.argv) > 2 else 256
    print(render(out, px))
