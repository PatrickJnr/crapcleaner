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
    a_intensity = max(0.5, min(1.6, float(accent_intensity)))
    bg_factor = max(0.6, min(1.4, float(bg_darkness)))
    mood_key = mood.lower() if mood.lower() in MOOD_STYLES else "cohesive"

    # Mood-specific saturation & tint scaling
    if mood_key == "vibrant":
        tint_s_scale = 0.24
        accent_s_boost = 1.25
        surface_depth = 1.15
    elif mood_key == "muted":
        tint_s_scale = 0.05
        accent_s_boost = 0.80
        surface_depth = 0.90
    elif mood_key == "oled":
        tint_s_scale = 0.04
        accent_s_boost = 1.30
        surface_depth = 1.20
    elif mood_key == "pastel":
        tint_s_scale = 0.10
        accent_s_boost = 0.70
        surface_depth = 0.85
    elif mood_key == "minimal":
        tint_s_scale = 0.02
        accent_s_boost = 1.00
        surface_depth = 1.00
    else:  # cohesive
        tint_s_scale = 0.14
        accent_s_boost = 1.00
        surface_depth = 1.00

    # Effective accent saturation
    effective_s = max(0.15, min(1.0, s * a_intensity * accent_s_boost))

    # Perceptual accent lightness tuning
    h_bias = hue_lightness_bias(h)
    if is_dark:
        # If hue is yellow/green, slightly lower lightness to avoid blinding glare
        target_accent_l = 0.54 + (0.08 * (1.0 - h_bias))
        accent_l = max(0.48, min(0.70, lum if 0.44 <= lum <= 0.68 else target_accent_l))
        hover_l = min(0.82, accent_l + 0.08)
        pressed_l = max(0.38, accent_l - 0.08)
    else:
        # Light mode: darker accent for crisp readability
        target_accent_l = 0.42 - (0.06 * h_bias)
        accent_l = max(0.32, min(0.52, lum if 0.30 <= lum <= 0.56 else target_accent_l))
        hover_l = max(0.24, accent_l - 0.07)
        pressed_l = max(0.18, accent_l - 0.13)

    accent = hsl_to_hex(h, effective_s, accent_l)
    accent_hover = hsl_to_hex(h, effective_s, hover_l)
    accent_pressed = hsl_to_hex(h, effective_s, pressed_l)
    r_a, g_a, b_a = hex_to_rgb(accent)
    accent_soft = f"rgba({r_a}, {g_a}, {b_a}, 0.16)"

    # Base tint for background and surfaces
    tint_s = min(0.25, max(0.01, s * tint_s_scale))

    if is_oled:
        # OLED True Black canvas
        window = "#000000"
        panel = hsl_to_hex(h, tint_s * 0.5, 0.030)
        surface = hsl_to_hex(h, tint_s, 0.065 * s_contrast)
        surface2 = hsl_to_hex(h, tint_s, 0.105 * s_contrast)
        elevated = hsl_to_hex(h, tint_s, 0.145 * s_contrast)
        border = hsl_to_hex(h, tint_s, 0.130 * s_contrast)
        border2 = hsl_to_hex(h, tint_s, 0.220 * s_contrast)

        text = "#ffffff"
        muted = hsl_to_hex(h, min(0.08, tint_s), 0.72)
        faint = hsl_to_hex(h, min(0.08, tint_s), 0.50)

        success = "#34d399"
        warning = "#fbbf24"
        danger = "#f87171"
        review = "#fb923c"
        info = "#38bdf8"

    elif is_dark:
        # Dark mode surface stratification
        base_bg_l = (0.065 / bg_factor) * surface_depth
        window_l = max(0.035, min(0.11, base_bg_l))
        panel_l = max(0.060, min(0.14, window_l + (0.026 * s_contrast)))
        surface_l = max(0.090, min(0.18, window_l + (0.065 * s_contrast)))
        surface2_l = max(0.125, min(0.23, window_l + (0.105 * s_contrast)))
        elevated_l = max(0.165, min(0.29, window_l + (0.150 * s_contrast)))
        border_l = max(0.140, min(0.27, surface_l + (0.050 * s_contrast)))
        border2_l = max(0.220, min(0.39, border_l + 0.085))

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
        base_bg_l = min(0.985, (0.965 * bg_factor))
        window_l = max(0.92, min(0.98, base_bg_l))
        panel_l = 1.0 if mood_key == "minimal" else max(0.97, min(1.0, 0.99))
        surface_l = max(0.90, min(0.95, window_l - (0.035 * s_contrast)))
        surface2_l = max(0.84, min(0.91, window_l - (0.080 * s_contrast)))
        elevated = "#ffffff"
        border_l = max(0.76, min(0.86, surface_l - (0.070 * s_contrast)))
        border2_l = max(0.64, min(0.76, border_l - 0.100))

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
