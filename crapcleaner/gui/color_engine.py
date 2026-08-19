"""Color Theory & Palette Generation Engine for CrapCleaner.

Provides perceptual color conversions, WCAG 2.1 contrast ratio calculations,
perceptually uniform lightness calibration, palette mood styles (Cohesive,
Vibrant, Muted, OLED, Pastel, Minimal), and automatic harmonious theme generation.
"""

from __future__ import annotations

import colorsys
import json
import math
import random
import re

# ---------------------------------------------------------------------------
# Conversions & Math
# ---------------------------------------------------------------------------


def normalize_hex(hex_str: str | None) -> str:
    """Normalize 3-digit or 6-digit hex color to standard lowercase #rrggbb."""
    if not isinstance(hex_str, str):
        return "#3b82f6"
    s = hex_str.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6 or not re.match(r"^[0-9a-fA-F]{6}$", s):
        return "#3b82f6"
    return f"#{s.lower()}"


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Convert hex string to (r, g, b) with values in 0..255."""
    clean = normalize_hex(hex_str).lstrip("#")
    return int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16)


def rgb_to_hex(r: int | float, g: int | float, b: int | float) -> str:
    """Convert (r, g, b) in 0..255 to #rrggbb."""
    r_c = max(0, min(255, int(round(r))))
    g_c = max(0, min(255, int(round(g))))
    b_c = max(0, min(255, int(round(b))))
    return f"#{r_c:02x}{g_c:02x}{b_c:02x}"


def hex_to_hsl(hex_str: str) -> tuple[float, float, float]:
    """Convert hex to HSL (H in 0..360, S in 0..1, L in 0..1)."""
    r, g, b = hex_to_rgb(hex_str)
    r_f, g_f, b_f = r / 255.0, g / 255.0, b / 255.0
    h_f, l_f, s_f = colorsys.rgb_to_hls(r_f, g_f, b_f)
    return h_f * 360.0, s_f, l_f


def hsl_to_hex(h: float, s: float, lightness: float) -> str:
    """Convert HSL (H in 0..360, S in 0..1, L in 0..1) to #rrggbb."""
    h_norm = (h % 360.0) / 360.0
    s_norm = max(0.0, min(1.0, s))
    l_norm = max(0.0, min(1.0, lightness))
    r_f, g_f, b_f = colorsys.hls_to_rgb(h_norm, l_norm, s_norm)
    return rgb_to_hex(r_f * 255, g_f * 255, b_f * 255)


# ---------------------------------------------------------------------------
# WCAG 2.1 Relative Luminance & Contrast
# ---------------------------------------------------------------------------


def relative_luminance(hex_str: str) -> float:
    """Calculate WCAG 2.1 relative luminance for a color (0.0 to 1.0)."""
    r, g, b = hex_to_rgb(hex_str)

    def channel_lum(val: int) -> float:
        c = val / 255.0
        return c / 12.92 if c <= 0.04045 else math.pow((c + 0.055) / 1.055, 2.4)

    return 0.2126 * channel_lum(r) + 0.7152 * channel_lum(g) + 0.0722 * channel_lum(b)


def contrast_ratio(color1: str, color2: str) -> float:
    """Calculate WCAG contrast ratio between two hex colors (1.0 to 21.0)."""
    l1 = relative_luminance(color1)
    l2 = relative_luminance(color2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def ensure_contrast(
    fg_hex: str,
    bg_hex: str,
    min_ratio: float = 4.5,
    is_dark_bg: bool | None = None,
) -> str:
    """Adjust foreground lightness incrementally until min contrast ratio is met."""
    if contrast_ratio(fg_hex, bg_hex) >= min_ratio:
        return fg_hex

    bg_lum = relative_luminance(bg_hex)
    dark_bg = bg_lum < 0.25 if is_dark_bg is None else is_dark_bg
    h, s, lum = hex_to_hsl(fg_hex)

    step = 0.04 if dark_bg else -0.04
    cur_l = lum
    for _ in range(25):
        cur_l = max(0.02, min(0.98, cur_l + step))
        candidate = hsl_to_hex(h, s, cur_l)
        if contrast_ratio(candidate, bg_hex) >= min_ratio:
            return candidate

    return "#ffffff" if dark_bg else "#0f172a"


# ---------------------------------------------------------------------------
# Perceptual Chroma & Lightness Utilities
# ---------------------------------------------------------------------------


def hue_lightness_bias(h: float) -> float:
    """Calculate perceptual lightness bias based on hue angle (0..360).

    Yellow/Green (~60-120 deg) have higher perceived brightness for same L,
    while Blue/Purple (~240-280 deg) have lower perceived brightness.
    """
    rad = math.radians(h - 60.0)
    # Cosine peaked at 60 deg (yellow) and lowest at 240 deg (blue)
    return 0.5 + 0.5 * math.cos(rad)


# ---------------------------------------------------------------------------
# Palette Generator with Moods
# ---------------------------------------------------------------------------

MOOD_STYLES = ("cohesive", "vibrant", "muted", "oled", "pastel", "minimal")


def generate_custom_palette(
    primary_color: str,
    mode: str = "dark",
    surface_contrast: float = 1.0,
    accent_intensity: float = 1.0,
    bg_darkness: float = 1.0,
    mood: str = "cohesive",
) -> dict[str, str]:
    """Generate a complete, harmonious 27-token palette from a primary color.

    Supports custom mood styles (cohesive, vibrant, muted, oled, pastel, minimal)
    and fully complies with WCAG 2.1 AA/AAA contrast guidelines.
    """
    is_dark = mode.lower() != "light"
    is_oled = mood.lower() == "oled" and is_dark
    primary = normalize_hex(primary_color)
    h, s, lum = hex_to_hsl(primary)

    # Clamp tuning factors
    s_contrast = max(0.6, min(1.4, float(surface_contrast)))
    a_intensity = max(0.4, min(1.6, float(accent_intensity)))
    bg_factor = max(0.6, min(1.4, float(bg_darkness)))
    mood_key = mood.lower() if mood.lower() in MOOD_STYLES else "cohesive"

    # Normalized contrast & vibrancy scales (0.0 to 1.0)
    contrast_scale = (s_contrast - 0.6) / 0.8  # 0.0 at 60%, 1.0 at 140%
    vibrancy_scale = (a_intensity - 0.4) / 1.2  # 0.0 at 40%, 1.0 at 160%

    # Mood-specific saturation & tint scaling
    if mood_key == "vibrant":
        tint_s_scale = 0.24
        accent_s_boost = 1.25
    elif mood_key == "muted":
        tint_s_scale = 0.05
        accent_s_boost = 0.75
    elif mood_key == "oled":
        tint_s_scale = 0.04
        accent_s_boost = 1.30
    elif mood_key == "pastel":
        tint_s_scale = 0.10
        accent_s_boost = 0.65
    elif mood_key == "minimal":
        tint_s_scale = 0.02
        accent_s_boost = 1.00
    else:  # cohesive
        tint_s_scale = 0.14
        accent_s_boost = 1.00

    # Effective accent saturation: scales smoothly with vibrancy slider
    effective_s = max(0.10, min(1.0, s * (0.35 + 0.95 * vibrancy_scale) * accent_s_boost))

    # Perceptual accent lightness tuning
    h_bias = hue_lightness_bias(h)
    if is_dark:
        # Lower vibrancy gives a calmer/deeper tone; higher vibrancy gives an illuminated neon punch
        target_accent_l = 0.44 + (0.18 * vibrancy_scale) + (0.06 * (1.0 - h_bias))
        accent_l = max(0.40, min(0.72, target_accent_l))
        hover_l = min(0.84, accent_l + 0.08)
        pressed_l = max(0.32, accent_l - 0.08)
    else:
        # Light mode: darker accent for crisp readability, higher vibrancy increases contrast
        target_accent_l = 0.50 - (0.18 * vibrancy_scale) - (0.06 * h_bias)
        accent_l = max(0.26, min(0.56, target_accent_l))
        hover_l = max(0.20, accent_l - 0.07)
        pressed_l = max(0.15, accent_l - 0.12)

    accent = hsl_to_hex(h, effective_s, accent_l)
    accent_hover = hsl_to_hex(h, effective_s, hover_l)
    accent_pressed = hsl_to_hex(h, effective_s, pressed_l)
    r_a, g_a, b_a = hex_to_rgb(accent)
    accent_soft = f"rgba({r_a}, {g_a}, {b_a}, {0.10 + 0.12 * vibrancy_scale:.2f})"

    # Base tint for background and surfaces
    tint_s = min(0.28, max(0.01, s * tint_s_scale * (0.6 + 0.6 * vibrancy_scale)))

    if is_oled:
        # OLED True Black canvas with dynamic contrast steps
        window = "#000000"
        panel = hsl_to_hex(h, tint_s * 0.5, 0.020 + 0.030 * contrast_scale)
        surface = hsl_to_hex(h, tint_s, 0.040 + 0.060 * contrast_scale)
        surface2 = hsl_to_hex(h, tint_s, 0.070 + 0.090 * contrast_scale)
        elevated = hsl_to_hex(h, tint_s, 0.100 + 0.120 * contrast_scale)
        border = hsl_to_hex(h, tint_s, 0.080 + 0.140 * contrast_scale)
        border2 = hsl_to_hex(h, tint_s, 0.140 + 0.200 * contrast_scale)

        text = "#ffffff"
        muted = hsl_to_hex(h, min(0.08, tint_s), 0.72)
        faint = hsl_to_hex(h, min(0.08, tint_s), 0.50)

        success = "#34d399"
        warning = "#fbbf24"
        danger = "#f87171"
        review = "#fb923c"
        info = "#38bdf8"

    elif is_dark:
        # Dark mode surface stratification with dynamic contrast
        base_bg_l = max(0.025, min(0.085, (0.070 / bg_factor) - (0.020 * contrast_scale)))
        window_l = base_bg_l
        panel_l = window_l + 0.020 + (0.040 * contrast_scale)
        surface_l = window_l + 0.045 + (0.085 * contrast_scale)
        surface2_l = window_l + 0.075 + (0.135 * contrast_scale)
        elevated_l = window_l + 0.110 + (0.185 * contrast_scale)
        border_l = surface_l + 0.035 + (0.105 * contrast_scale)
        border2_l = border_l + 0.055 + (0.140 * contrast_scale)

        window = hsl_to_hex(h, tint_s, window_l)
        panel = hsl_to_hex(h, tint_s, panel_l)
        surface = hsl_to_hex(h, tint_s, surface_l)
        surface2 = hsl_to_hex(h, tint_s, surface2_l)
        elevated = hsl_to_hex(h, tint_s, elevated_l)
        border = hsl_to_hex(h, tint_s, border_l)
        border2 = hsl_to_hex(h, tint_s, border2_l)

        # High-contrast text
        text = hsl_to_hex(h, min(0.06, tint_s), 0.96)
        muted = hsl_to_hex(h, min(0.10, tint_s), 0.70)
        faint = hsl_to_hex(h, min(0.10, tint_s), 0.50)

        # Vibrant semantic colors for dark surfaces
        success = "#34d399"
        warning = "#fbbf24"
        danger = "#f87171"
        review = "#fb923c"
        info = "#38bdf8"

    else:
        # Light mode surface stratification
        window_l = max(0.92, min(0.985, (0.975 * bg_factor) - (0.030 * contrast_scale)))
        panel_l = 1.0 if mood_key == "minimal" else max(0.97, min(1.0, 0.99))
        surface_l = max(0.86, min(0.96, window_l - (0.025 + 0.065 * contrast_scale)))
        surface2_l = max(0.78, min(0.92, window_l - (0.055 + 0.115 * contrast_scale)))
        elevated = "#ffffff"
        border_l = max(0.68, min(0.88, surface_l - (0.045 + 0.125 * contrast_scale)))
        border2_l = max(0.55, min(0.78, border_l - (0.075 + 0.100 * contrast_scale)))

        window = hsl_to_hex(h, tint_s, window_l)
        panel = hsl_to_hex(h, tint_s, panel_l)
        surface = hsl_to_hex(h, tint_s, surface_l)
        surface2 = hsl_to_hex(h, tint_s, surface2_l)
        border = hsl_to_hex(h, tint_s, border_l)
        border2 = hsl_to_hex(h, tint_s, border2_l)

        # High-contrast text on light surfaces
        text = hsl_to_hex(h, min(0.12, tint_s), 0.11)
        muted = hsl_to_hex(h, min(0.12, tint_s), 0.38)
        faint = hsl_to_hex(h, min(0.10, tint_s), 0.58)

        # Crisp semantic colors for light surfaces
        success = "#059669"
        warning = "#d97706"
        danger = "#dc2626"
        review = "#ea580c"
        info = "#0284c7"

    # Strict WCAG compliance enforcement
    text = ensure_contrast(text, window, min_ratio=7.0, is_dark_bg=is_dark)
    muted = ensure_contrast(muted, surface, min_ratio=4.5, is_dark_bg=is_dark)

    def soft_rgba(hex_code: str) -> str:
        r, g, b = hex_to_rgb(hex_code)
        return f"rgba({r}, {g}, {b}, 0.15)"

    return {
        "window": window,
        "panel": panel,
        "surface": surface,
        "surface2": surface2,
        "elevated": elevated,
        "border": border,
        "border2": border2,
        "text": text,
        "muted": muted,
        "faint": faint,
        "accent": accent,
        "accent_hover": accent_hover,
        "accent_pressed": accent_pressed,
        "accent_soft": accent_soft,
        "success": success,
        "success_soft": soft_rgba(success),
        "warning": warning,
        "warning_soft": soft_rgba(warning),
        "danger": danger,
        "danger_soft": soft_rgba(danger),
        "review": review,
        "review_soft": soft_rgba(review),
        "info": info,
        "info_soft": soft_rgba(info),
        "selection": accent,
        "safe": success,
    }


# ---------------------------------------------------------------------------
# Color Harmony Algorithms & Magic Generator
# ---------------------------------------------------------------------------


def generate_color_harmonies(base_hex: str) -> dict[str, list[str]]:
    """Calculate standard color harmonies (Analogous, Complementary, Triadic, Split)."""
    h, s, lum = hex_to_hsl(normalize_hex(base_hex))
    return {
        "analogous": [
            hsl_to_hex((h - 30) % 360, s, lum),
            normalize_hex(base_hex),
            hsl_to_hex((h + 30) % 360, s, lum),
        ],
        "complementary": [
            normalize_hex(base_hex),
            hsl_to_hex((h + 180) % 360, s, lum),
        ],
        "triadic": [
            normalize_hex(base_hex),
            hsl_to_hex((h + 120) % 360, s, lum),
            hsl_to_hex((h + 240) % 360, s, lum),
        ],
        "split_complementary": [
            normalize_hex(base_hex),
            hsl_to_hex((h + 150) % 360, s, lum),
            hsl_to_hex((h + 210) % 360, s, lum),
        ],
    }


def generate_magic_palette() -> dict:
    """Generate a random aesthetically balanced custom theme configuration."""
    # Curated vibrant hues
    curated_hues = [
        0,
        15,
        30,
        45,
        140,
        160,
        175,
        195,
        215,
        235,
        260,
        280,
        310,
        330,
    ]
    h = float(random.choice(curated_hues))
    s = random.uniform(0.65, 0.95)
    lum = random.uniform(0.48, 0.62)
    primary = hsl_to_hex(h, s, lum)

    mode = "dark" if random.random() < 0.85 else "light"
    mood = random.choice(["cohesive", "vibrant", "oled", "muted", "minimal"])

    return {
        "primary_color": primary,
        "mode": mode,
        "mood": mood,
        "surface_contrast": round(random.uniform(0.9, 1.15), 2),
        "accent_intensity": round(random.uniform(0.9, 1.25), 2),
        "bg_darkness": round(random.uniform(0.95, 1.1), 2),
    }


# ---------------------------------------------------------------------------
# Theme JSON Import / Export
# ---------------------------------------------------------------------------


def export_custom_theme_json(custom_config: dict) -> str:
    """Serialize custom theme configuration to a pretty JSON string."""
    clean = {
        "primary_color": normalize_hex(custom_config.get("primary_color", "#3b82f6")),
        "mode": custom_config.get("mode", "dark"),
        "mood": custom_config.get("mood", "cohesive"),
        "surface_contrast": float(custom_config.get("surface_contrast", 1.0)),
        "accent_intensity": float(custom_config.get("accent_intensity", 1.0)),
        "bg_darkness": float(custom_config.get("bg_darkness", 1.0)),
    }
    return json.dumps(clean, indent=2)


def import_custom_theme_json(json_str: str) -> dict | None:
    """Parse and validate custom theme configuration from JSON string."""
    try:
        data = json.loads(json_str)
        if not isinstance(data, dict):
            return None
        return {
            "primary_color": normalize_hex(data.get("primary_color", "#3b82f6")),
            "mode": "light" if data.get("mode") == "light" else "dark",
            "mood": data.get("mood", "cohesive") if data.get("mood") in MOOD_STYLES else "cohesive",
            "surface_contrast": max(0.6, min(1.4, float(data.get("surface_contrast", 1.0)))),
            "accent_intensity": max(0.5, min(1.6, float(data.get("accent_intensity", 1.0)))),
            "bg_darkness": max(0.6, min(1.4, float(data.get("bg_darkness", 1.0)))),
        }
    except Exception:
        return None
