"""Tests for the theme palettes and the theme cross-fade helper."""

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
    for expected in ("dark", "light", "oled", "high-contrast", "adwaita-dark", "adwaita-light"):
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
    # Not identity: every palette gains the derived label colours on the way out.
    assert palette_for("nonsense") == palette_for("dark")
    assert palette_for("nonsense")["window"] == DARK["window"]
    assert palette_for("nonsense")["accent"] == DARK["accent"]
    assert theme_label("dark") == "Dark (default)"
    assert theme_label("nonsense") == "Nonsense"


def test_apply_theme_sets_a_stylesheet_per_theme(qt_app):
    from crapcleaner.gui.theme import _build_stylesheet

    for theme in THEMES:
        css = _build_stylesheet(PALETTES[theme])
        assert PALETTES[theme]["window"] in css
    apply_theme(qt_app, "dark")
    assert PALETTES["dark"]["window"] in qt_app.styleSheet()
    apply_theme(qt_app, "light")
    assert PALETTES["light"]["window"] in qt_app.styleSheet()


def test_fade_runs_the_swap_even_without_a_visible_window(qt_app):
    from PySide6.QtWidgets import QWidget

    window = QWidget()
    calls = []
    fade_theme_change(window, lambda: calls.append(True), duration_ms=0)
    assert calls == [True]
    window.deleteLater()
    qt_app.processEvents()


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
    if hasattr(window, "_theme_fade_overlay") and window._theme_fade_overlay:
        window._theme_fade_overlay.deleteLater()
    window.close()
    window.deleteLater()
    qt_app.processEvents()


def test_extended_theme_set_is_available():
    for expected in (
        "midnight",
        "slate",
        "forest",
        "cyberpunk",
        "dracula",
        "monokai",
        "oceanic",
        "tokyo-night",
        "nord",
        "sunset",
        "matrix",
        "coffee",
        "rose-pine",
        "gruvbox",
        "synthwave",
        "amber-crt",
        "crimson",
        "emerald",
        "solar-eclipse",
        "one-dark",
        "cobalt",
        "mint-choco",
        "matcha",
        "bubblegum",
        "lavender",
        "parchment",
        "coffee",
        "adwaita-dark",
        "adwaita-light",
    ):
        assert expected in THEMES
        assert theme_label(expected) != expected


def test_oled_theme_uses_true_black_backgrounds():
    oled = PALETTES["oled"]
    assert oled["window"] == "#000000"
    assert int(oled["panel"].lstrip("#"), 16) < int(PALETTES["dark"]["panel"].lstrip("#"), 16)
    assert oled["text"].lower() not in (oled["window"].lower(), oled["panel"].lower())


def test_theme_categories_and_metadata_complete():
    from crapcleaner.gui.theme import (
        THEME_CATEGORIES,
        get_theme_category,
        get_theme_category_label,
        get_theme_description,
        get_theme_swatches,
        is_dark_theme,
    )

    for theme_id in THEMES:
        cat_id = get_theme_category(theme_id)
        assert cat_id in THEME_CATEGORIES, f"Theme {theme_id} has invalid category {cat_id}"
        cat_label = get_theme_category_label(theme_id)
        assert cat_label == THEME_CATEGORIES[cat_id]

        desc = get_theme_description(theme_id)
        assert len(desc) > 5

        swatches = get_theme_swatches(theme_id)
        assert len(swatches) == 5
        for s in swatches:
            assert s.startswith("#") or s.startswith("rgba")

        dark = is_dark_theme(theme_id)
        assert isinstance(dark, bool)


def test_theme_card_component(qt_app):
    from crapcleaner.gui.theme_picker import ThemeCard

    card = ThemeCard("tokyo-night")
    assert card.theme_id == "tokyo-night"
    assert "Tokyo Night" in card.title_label.text()
    assert not card._is_active

    card.set_active(True)
    assert card._is_active
    assert not card.active_badge.isHidden()

    signals = []
    card.clicked.connect(signals.append)
    card.clicked.emit("tokyo-night")
    assert signals == ["tokyo-night"]


def test_theme_gallery_widget_filtering_and_selection(qt_app):
    from crapcleaner.gui.theme_picker import ThemeGalleryWidget

    gallery = ThemeGalleryWidget("dark")
    assert gallery.current_theme() == "dark"
    assert gallery.theme_combo.currentData() == "dark"

    # Counts are derived, not hard-coded: a theme the user drops into their theme
    # directory is a real theme and must not fail the suite.
    from crapcleaner.gui.theme import THEME_CATEGORIES, get_theme_category

    chip_texts = [button.text().replace("&&", "&") for button in gallery.chip_group.buttons()]
    for category_id, label in THEME_CATEGORIES.items():
        count = sum(1 for t in THEMES if get_theme_category(t) == category_id)
        assert f"{label} ({count})" in chip_texts
    assert f"All ({len(THEMES)})" in chip_texts

    changed_signals = []
    gallery.theme_changed.connect(changed_signals.append)
    gallery.select_theme("nord")
    assert gallery.current_theme() == "nord"
    assert gallery.theme_combo.currentData() == "nord"
    assert changed_signals == ["nord"]
    assert gallery.hero_name_label.text() == "Nordic Frost"

    gallery.select_theme("adwaita-dark")
    assert gallery.current_theme() == "adwaita-dark"
    assert gallery.hero_name_label.text() == "Adwaita Dark"

    gallery._on_category_selected("retro")
    visible_retro_cards = [c for c in gallery._cards.values() if not c.isHidden()]
    assert len(visible_retro_cards) == 8
    assert not gallery._cards["windows-95"].isHidden()
    assert gallery._cards["dark"].isHidden()

    gallery._on_category_selected("light")
    visible_light_cards = [c for c in gallery._cards.values() if not c.isHidden()]
    assert len(visible_light_cards) == 5
    assert not gallery._cards["adwaita-light"].isHidden()

    gallery._on_category_selected("all")
    gallery._on_search_changed("dracula")
    visible_search_cards = [c for c in gallery._cards.values() if not c.isHidden()]
    assert len(visible_search_cards) == 1
    assert not gallery._cards["dracula"].isHidden()

    gallery._on_search_changed("")
    visible_all_cards = [c for c in gallery._cards.values() if not c.isHidden()]
    assert len(visible_all_cards) == len(THEMES)

    gallery._select_random_theme()
    assert gallery.current_theme() in THEMES
