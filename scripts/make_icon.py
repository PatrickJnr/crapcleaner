"""Render the application icon to a multi-resolution .ico file.

The window icon is drawn at runtime by `crapcleaner.gui.theme.make_window_icon`, so
the packaged executable had no icon of its own - it shipped with PyInstaller's
default, which is the first thing a new user sees and the last thing that makes an
unsigned download look trustworthy.

The .ico is generated here and committed, so building needs no Qt and the icon in a
release is exactly the icon that was reviewed. Re-run this after changing the brand
mark:

    python scripts/make_icon.py

Entries are stored as PNG, which every Windows version since Vista reads and which
avoids hand-rolling BMP masks.
"""

from __future__ import annotations

import os
import struct

SIZES = (16, 24, 32, 48, 64, 128, 256)
OUTPUT = os.path.join("crapcleaner", "assets", "crapcleaner.ico")


def _render_png(size: int) -> bytes:
    """Draw the brand mark at `size` and return it as PNG bytes."""
    from PySide6.QtCore import QBuffer, QByteArray, QRectF, Qt
    from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen, QPixmap

    from crapcleaner.gui.icons import draw_glyph

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)

    inset = max(1.0, size * 0.03)
    rect = QRectF(inset, inset, size - inset * 2, size - inset * 2)
    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradient.setColorAt(0.0, QColor("#2563eb"))
    gradient.setColorAt(1.0, QColor("#60a5fa"))
    painter.setBrush(QBrush(gradient))
    painter.setPen(QPen(QColor("#3b82f6"), max(1.0, size / 64.0)))
    painter.drawRoundedRect(rect, size * 0.22, size * 0.22)
    draw_glyph(painter, rect, "brand", "#ffffff", int(size * 0.6))
    painter.end()

    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    buffer.close()
    return bytes(data)


def build_ico(images: dict[int, bytes]) -> bytes:
    """Pack `{size: png_bytes}` into an ICO container."""
    count = len(images)
    header = struct.pack("<HHH", 0, 1, count)
    offset = len(header) + count * 16

    directory = b""
    body = b""
    for size in sorted(images):
        payload = images[size]
        directory += struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,  # 0 means 256
            0 if size >= 256 else size,
            0,  # palette size, 0 for true colour
            0,  # reserved
            1,  # colour planes
            32,  # bits per pixel
            len(payload),
            offset,
        )
        body += payload
        offset += len(payload)
    return header + directory + body


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance() or QGuiApplication([])
    images = {size: _render_png(size) for size in SIZES}
    del app

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "wb") as fh:
        fh.write(build_ico(images))
    print(f"wrote {OUTPUT} ({os.path.getsize(OUTPUT):,} bytes, {len(SIZES)} sizes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
