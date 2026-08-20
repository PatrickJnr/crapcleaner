"""Render assets/social_preview.svg to a 1280x640 PNG image.

Uses headless Chromium/Edge for full CSS/SVG filter/shadow support,
falling back to PySide6 QtSvg if a browser is not available.
"""

import os
import shutil
import subprocess


def find_browser() -> str | None:
    """Find available Chrome or Edge binary for full-fidelity SVG rasterization."""
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "google-chrome",
        "chromium",
        "chromium-browser",
        "msedge",
        "edge",
    ]
    for c in candidates:
        if os.path.isabs(c) and os.path.isfile(c):
            return c
        path = shutil.which(c)
        if path:
            return path
    return None


def render_svg_to_png(svg_path: str, png_path: str, width: int = 1280, height: int = 640) -> bool:
    svg_path = os.path.abspath(svg_path)
    png_path = os.path.abspath(png_path)
    os.makedirs(os.path.dirname(png_path), exist_ok=True)

    if not os.path.exists(svg_path):
        print(f"Error: SVG file not found: {svg_path}")
        return False

    browser = find_browser()
    if browser:
        svg_url = f"file:///{svg_path.replace(os.sep, '/')}"
        cmd = [
            browser,
            "--headless",
            "--disable-gpu",
            "--force-device-scale-factor=1",
            f"--window-size={width},{height}",
            f"--screenshot={png_path}",
            svg_url,
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if res.returncode == 0 and os.path.exists(png_path) and os.path.getsize(png_path) > 0:
                print(
                    f"Successfully rendered {width}x{height} PNG via {os.path.basename(browser)}: {png_path} ({os.path.getsize(png_path)} bytes)"
                )
                return True
        except Exception as exc:
            print(f"Browser rasterization warning: {exc}, falling back to PySide6...")

    try:
        from PySide6.QtCore import QByteArray, QSize
        from PySide6.QtGui import QColor, QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtWidgets import QApplication

        QApplication.instance() or QApplication([])

        with open(svg_path, "rb") as f:
            svg_data = f.read()

        renderer = QSvgRenderer(QByteArray(svg_data))
        if not renderer.isValid():
            print(f"Error: Invalid SVG in {svg_path}")
            return False

        image = QImage(QSize(width, height), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor(0, 0, 0, 0))

        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        renderer.render(painter)
        painter.end()

        success = image.save(png_path, "PNG", quality=100)
        if success:
            print(
                f"Successfully rendered {width}x{height} PNG via PySide6: {png_path} ({os.path.getsize(png_path)} bytes)"
            )
        return success
    except Exception as exc:
        print(f"Error rendering PNG: {exc}")
        return False


if __name__ == "__main__":
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    svg_file = os.path.join(base_dir, "assets", "social_preview.svg")
    png_file = os.path.join(base_dir, "assets", "social_preview.png")

    gh_svg = os.path.join(base_dir, ".github", "social_preview.svg")
    gh_png = os.path.join(base_dir, ".github", "social_preview.png")

    with open(svg_file, encoding="utf-8") as src:
        svg_content = src.read()
    with open(gh_svg, "w", encoding="utf-8") as dst:
        dst.write(svg_content)

    render_svg_to_png(svg_file, png_file, 1280, 640)
    render_svg_to_png(gh_svg, gh_png, 1280, 640)
