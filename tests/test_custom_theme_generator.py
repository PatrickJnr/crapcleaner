"""Comprehensive tests for the Custom Theme Generator and Palette Engine."""

import pytest

from crapcleaner.config import update_settings
from crapcleaner.gui.color_engine import (
    MOOD_STYLES,
    contrast_ratio,
    ensure_contrast,
    export_custom_theme_json,
    generate_color_harmonies,
    generate_custom_palette,
    generate_magic_palette,
    hex_to_hsl,
    hex_to_rgb,
    hsl_to_hex,
    import_custom_theme_json,
    normalize_hex,
    relative_luminance,
    rgb_to_hex,
)
from crapcleaner.gui.theme import (
    THEMES,
    get_theme_category,
    get_theme_description,
    get_theme_swatches,
    invalidate_custom_theme_cache,
    is_dark_theme,
    palette_for,
    theme_label,
)

# ---------------------------------------------------------------------------
# 1. Color Math & Conversions
# ---------------------------------------------------------------------------


def test_normalize_hex():
    assert normalize_hex("#fff") == "#ffffff"
    assert normalize_hex("#3B82F6") == "#3b82f6"
    assert normalize_hex("10b981") == "#10b981"
    assert normalize_hex("invalid") == "#3b82f6"
    assert normalize_hex(None) == "#3b82f6"


def test_rgb_hex_roundtrip():
    for r, g, b in [(0, 0, 0), (255, 255, 255), (59, 130, 246), (220, 38, 38)]:
        h = rgb_to_hex(r, g, b)
        assert hex_to_rgb(h) == (r, g, b)


def test_hsl_hex_roundtrip():
    for h, s, lum in [(0.0, 1.0, 0.5), (120.0, 0.5, 0.5), (240.0, 0.8, 0.6)]:
        hex_val = hsl_to_hex(h, s, lum)
        h2, s2, l2 = hex_to_hsl(hex_val)
        assert abs(h - h2) < 2.0
        assert abs(s - s2) < 0.05
        assert abs(lum - l2) < 0.05


# ---------------------------------------------------------------------------
# 2. Relative Luminance & Contrast Ratio
# ---------------------------------------------------------------------------


def test_relative_luminance():
    assert relative_luminance("#000000") == pytest.approx(0.0, abs=1e-3)
    assert relative_luminance("#ffffff") == pytest.approx(1.0, abs=1e-3)


def test_contrast_ratio_known_pairs():
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0, rel=1e-2)
    assert contrast_ratio("#3b82f6", "#3b82f6") == pytest.approx(1.0, rel=1e-2)


def test_ensure_contrast():
    adjusted = ensure_contrast("#222222", "#000000", min_ratio=4.5)
    assert contrast_ratio(adjusted, "#000000") >= 4.5

    adjusted_light = ensure_contrast("#dddddd", "#ffffff", min_ratio=4.5)
    assert contrast_ratio(adjusted_light, "#ffffff") >= 4.5


# ---------------------------------------------------------------------------
# 3. Palette Generation & Required Tokens
# ---------------------------------------------------------------------------

REQUIRED_TOKENS = {
    "window",
    "panel",
    "surface",
    "surface2",
    "elevated",
    "border",
    "border2",
    "text",
    "muted",
    "faint",
    "accent",
    "accent_hover",
    "accent_pressed",
    "accent_soft",
    "success",
    "success_soft",
    "warning",
    "warning_soft",
    "danger",
    "danger_soft",
    "review",
    "review_soft",
    "info",
    "info_soft",
    "selection",
    "safe",
}


def test_palette_contains_all_tokens():
    for mode in ("dark", "light"):
        for mood in MOOD_STYLES:
            pal = generate_custom_palette("#3b82f6", mode=mode, mood=mood)
            assert REQUIRED_TOKENS.issubset(pal.keys())


# ---------------------------------------------------------------------------
# 4. WCAG Contrast Compliance across Hues and Modes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mode,hex_color",
    [
        ("dark", "#3b82f6"),  # Blue
        ("dark", "#10b981"),  # Green
        ("dark", "#8b5cf6"),  # Purple
        ("dark", "#f59e0b"),  # Amber
        ("dark", "#f43f5e"),  # Rose
        ("dark", "#06b6d4"),  # Cyan
        ("dark", "#64748b"),  # Slate
        ("dark", "#dc2626"),  # Red
        ("light", "#3b82f6"),
        ("light", "#10b981"),
        ("light", "#8b5cf6"),
        ("light", "#f59e0b"),
        ("light", "#f43f5e"),
        ("light", "#06b6d4"),
        ("light", "#64748b"),
        ("light", "#dc2626"),
    ],
)
def test_palette_wcag_contrast_standards(mode, hex_color):
    pal = generate_custom_palette(hex_color, mode=mode)
    cr_window = contrast_ratio(pal["text"], pal["window"])
    assert cr_window >= 4.5, f"{mode} text against window failed contrast ({cr_window:.2f})"

    cr_surface = contrast_ratio(pal["muted"], pal["surface"])
    assert cr_surface >= 3.0, f"{mode} muted against surface failed contrast ({cr_surface:.2f})"


# ---------------------------------------------------------------------------
# 5. Palette Mood Presets (Cohesive, Vibrant, Muted, OLED, Pastel, Minimal)
# ---------------------------------------------------------------------------


def test_palette_mood_styles():
    for mood in MOOD_STYLES:
        pal_dark = generate_custom_palette("#3b82f6", mode="dark", mood=mood)
        pal_light = generate_custom_palette("#3b82f6", mode="light", mood=mood)
        assert REQUIRED_TOKENS.issubset(pal_dark.keys())
        assert REQUIRED_TOKENS.issubset(pal_light.keys())

    # OLED mode has true black window
    pal_oled = generate_custom_palette("#3b82f6", mode="dark", mood="oled")
    assert pal_oled["window"] == "#000000"


# ---------------------------------------------------------------------------
# 6. Color Harmonies & Magic Generator
# ---------------------------------------------------------------------------


def test_color_harmonies():
    harmonies = generate_color_harmonies("#3b82f6")
    assert "analogous" in harmonies
    assert "complementary" in harmonies
    assert "triadic" in harmonies
    assert "split_complementary" in harmonies
    assert len(harmonies["analogous"]) == 3
    assert len(harmonies["complementary"]) == 2


def test_magic_palette_generator():
    magic = generate_magic_palette()
    assert "primary_color" in magic
    assert "mode" in magic
    assert "mood" in magic
    assert magic["mode"] in ("dark", "light")
    assert magic["mood"] in MOOD_STYLES
    pal = generate_custom_palette(magic["primary_color"], mode=magic["mode"], mood=magic["mood"])
    assert REQUIRED_TOKENS.issubset(pal.keys())


# ---------------------------------------------------------------------------
# 7. JSON Export & Import
# ---------------------------------------------------------------------------


def test_theme_json_export_import():
    cfg = {
        "primary_color": "#8b5cf6",
        "mode": "dark",
        "mood": "vibrant",
        "surface_contrast": 1.1,
        "accent_intensity": 1.2,
        "bg_darkness": 1.0,
    }
    json_str = export_custom_theme_json(cfg)
    assert "#8b5cf6" in json_str
    assert "vibrant" in json_str

    imported = import_custom_theme_json(json_str)
    assert imported is not None
    assert imported["primary_color"] == "#8b5cf6"
    assert imported["mood"] == "vibrant"
    assert imported["mode"] == "dark"

    # Invalid JSON
    assert import_custom_theme_json("invalid json") is None
    assert import_custom_theme_json("[]") is None


# ---------------------------------------------------------------------------
# 8. Edge Case Colors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "edge_color",
    [
        "#000000",  # Pure black
        "#ffffff",  # Pure white
        "#ffff00",  # Pure yellow
        "#050505",  # Extremely dark
        "#808080",  # 50% neutral grey
        "#e0d7ff",  # Very light pastel
        "not-a-hex",  # Invalid string fallback
    ],
)
def test_edge_case_colors_generate_valid_palettes(edge_color):
    pal_dark = generate_custom_palette(edge_color, mode="dark")
    pal_light = generate_custom_palette(edge_color, mode="light")
    assert REQUIRED_TOKENS.issubset(pal_dark.keys())
    assert REQUIRED_TOKENS.issubset(pal_light.keys())


# ---------------------------------------------------------------------------
# 9. Theme Engine & Persistence Integration
# ---------------------------------------------------------------------------


def test_custom_theme_in_theme_registry():
    assert "custom" in THEMES
    assert theme_label("custom") == "Custom Theme"
    assert get_theme_category("custom") == "custom"
    assert "chosen primary color" in get_theme_description("custom")
    assert len(get_theme_swatches("custom")) == 5


def test_custom_theme_palette_resolution_and_cache():
    invalidate_custom_theme_cache()
    update_settings(
        custom_theme={
            "primary_color": "#10b981",
            "mode": "dark",
            "mood": "cohesive",
            "surface_contrast": 1.0,
            "accent_intensity": 1.0,
            "bg_darkness": 1.0,
        }
    )
    pal = palette_for("custom")
    assert pal["accent"] != ""
    assert is_dark_theme("custom") is True

    # Switching to light mode
    invalidate_custom_theme_cache()
    update_settings(
        custom_theme={
            "primary_color": "#10b981",
            "mode": "light",
            "mood": "cohesive",
            "surface_contrast": 1.0,
            "accent_intensity": 1.0,
            "bg_darkness": 1.0,
        }
    )
    pal_light = palette_for("custom")
    assert is_dark_theme("custom") is False
    assert pal_light["window"] != pal["window"]
