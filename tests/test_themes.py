"""Tests for the theme palettes and the theme cross-fade helper."""

import pytest

from crapcleaner.gui.theme import (
    DARK,
    PALETTES,
    THEMES,
    apply_theme,
    fade_theme_change,
    palette_for,
    theme_label,
)


def test_all_themes_are_registered():
    assert set(THEMES) == set(PALETTES)
    for expected in ("dark", "light", "oled", "high-contrast"):
        assert expected in THEMES


def test_palettes_define_the_same_tokens():
    reference = set(DARK)
    for name, palette in PALETTES.items():
        assert set(palette) == reference, f"{name} palette has mismatched tokens"


def test_status_colors_are_distinct_per_theme():
    for name, palette in PALETTES.items():
        status = {palette["success"], palette["warning"], palette["danger"], palette["accent"]}
        assert len(status) == 4, f"{name} reuses a status color"


def test_text_and_background_differ():
    for name, palette in PALETTES.items():
        assert palette["text"].lower() != palette["window"].lower(), name
        assert palette["text"].lower() != palette["panel"].lower(), name


def test_unknown_theme_falls_back_to_dark():
    assert palette_for("nonsense") is DARK
    assert theme_label("dark") == "Dark (default)"
    assert theme_label("nonsense") == "Nonsense"


def test_apply_theme_sets_a_stylesheet_per_theme(qt_app):
    for theme in THEMES:
        apply_theme(qt_app, theme)
        stylesheet = qt_app.styleSheet()
        assert PALETTES[theme]["window"] in stylesheet


def test_fade_runs_the_swap_even_without_a_visible_window(qt_app):
    from PySide6.QtWidgets import QWidget

    window = QWidget()
    calls = []
    fade_theme_change(window, lambda: calls.append(True), duration_ms=0)
    assert calls == [True]


def test_fade_with_visible_window_does_not_block(qt_app):
    from PySide6.QtWidgets import QWidget

    window = QWidget()
    window.resize(120, 80)
    window.show()
    qt_app.processEvents()
    calls = []
    fade_theme_change(window, lambda: calls.append(True), duration_ms=40)
    assert calls == [True]
    qt_app.processEvents()
    window.close()


@pytest.fixture
def qt_app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_extended_theme_set_is_available():
    for expected in ("midnight", "slate", "forest"):
        assert expected in THEMES
        assert theme_label(expected) != expected


def test_oled_theme_uses_true_black_backgrounds():
    oled = PALETTES["oled"]
    assert oled["window"] == "#000000"
    assert int(oled["panel"].lstrip("#"), 16) < int(PALETTES["dark"]["panel"].lstrip("#"), 16)
    assert oled["text"].lower() not in (oled["window"].lower(), oled["panel"].lower())
