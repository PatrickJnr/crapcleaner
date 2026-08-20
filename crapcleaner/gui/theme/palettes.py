"""Theme palettes, loaded from data.

Every colour scheme is a JSON file under ``crapcleaner/assets/themes``:

    {
      "id": "dracula",
      "label": "Dracula",
      "category": "code-palettes",
      "description": "...",
      "order": 12,
      "colors": {"accent": "#bd93f9", ...}
    }

A file dropped into ``<config dir>/themes`` is loaded the same way, so a theme
can be added or shared without touching Python. A file missing a colour, or
carrying something that is not a hex colour, is skipped with a warning rather
than breaking start-up.

Text colours are raised to meet WCAG AA against the backgrounds the stylesheet
actually draws them on - see :data:`CONTRAST_EXEMPTIONS`.
"""

import json
import os
import re

from crapcleaner.utils.logs import get_logger

logger = get_logger("theme")

#: Every colour a palette must define. A file missing one of these is rejected
#: rather than silently rendering a widget with an empty colour.
REQUIRED_TOKENS = [
    "accent",
    "accent_hover",
    "accent_pressed",
    "accent_soft",
    "border",
    "border2",
    "danger",
    "danger_soft",
    "elevated",
    "faint",
    "info",
    "info_soft",
    "muted",
    "panel",
    "review",
    "review_soft",
    "safe",
    "selection",
    "success",
    "success_soft",
    "surface",
    "surface2",
    "text",
    "warning",
    "warning_soft",
    "window",
]

#: Qt stylesheets take hex or rgb()/rgba(), and the soft accent tokens use rgba.
#: Category ids the gallery has a filter chip for. A theme naming anything else
#: is filed under the closest thing that exists, so it stays reachable.
THEME_CATEGORIES = {
    "modern-dark": "Modern Dark",
    "light": "Light & Pastel",
    "retro": "Retro & Vintage",
    "cyber": "Cyber & Synth",
    "code": "Code Palettes",
    "nature": "Warm & Nature",
    "custom": "Custom",
}

DEFAULT_CATEGORY = "modern-dark"
#: Every theme this project ships. Membership decides whether a theme is ours, so a
#: file dropped into any theme directory is the user's regardless of where it sits or
#: what its `category` says - which is what puts it in Custom, and what makes Edit and
#: Delete safe to offer for it.
BUILTIN_THEME_IDS: frozenset[str] = frozenset(
    (
        "adwaita-dark",
        "adwaita-light",
        "amber-crt",
        "analog-horror",
        "arctic",
        "black-mesa",
        "bubblegum",
        "cobalt",
        "coffee",
        "commodore-64",
        "crimson",
        "custom",
        "cyberpunk",
        "dark",
        "dracula",
        "emerald",
        "forest",
        "gameboy",
        "graphite",
        "gruvbox",
        "high-contrast",
        "lavender",
        "light",
        "matcha",
        "matrix",
        "midnight",
        "mint-choco",
        "monokai",
        "nord",
        "oceanic",
        "oled",
        "one-dark",
        "parchment",
        "pulp-seventies",
        "rose-pine",
        "slate",
        "solar-eclipse",
        "solarized-dark",
        "sunset",
        "synthwave",
        "tokyo-night",
        "vaporwave",
        "vault",
        "windows-95",
    )
)

#: Where a theme the user added or wrote is filed.
USER_CATEGORY = "custom"


_COLOR = re.compile(
    r"^(?:#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})"
    r"|rgba?\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*(?:,\s*[0-9.]+\s*)?\))$"
)

BUNDLED_THEME_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "assets",
    "themes",
)


def user_theme_dir() -> str:
    """Where a user's own theme files live."""
    from crapcleaner.config import config_dir

    return os.path.join(config_dir(), "themes")


def _valid_colors(name: str, colors: object) -> dict[str, str] | None:
    if not isinstance(colors, dict):
        logger.warning("Theme %r has no colours", name)
        return None
    missing = [token for token in REQUIRED_TOKENS if token not in colors]
    if missing:
        logger.warning("Theme %r is missing %s", name, ", ".join(sorted(missing)))
        return None
    bad = [k for k, v in colors.items() if not isinstance(v, str) or not _COLOR.match(v)]
    if bad:
        logger.warning("Theme %r has invalid colours: %s", name, ", ".join(sorted(bad)))
        return None
    return {str(k): str(v) for k, v in colors.items()}


def _load_dir(directory: str, source: str) -> list[dict]:
    themes: list[dict] = []
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return themes

    for filename in names:
        if not filename.endswith(".json"):
            continue
        path = os.path.join(directory, filename)
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            logger.warning("Could not read the theme file %s", filename, exc_info=True)
            continue
        if not isinstance(data, dict):
            logger.warning("Theme file %s does not contain an object", filename)
            continue

        name = str(data.get("id") or os.path.splitext(filename)[0])
        colors = _valid_colors(name, data.get("colors"))
        if colors is None:
            continue
        is_builtin = name in BUILTIN_THEME_IDS
        category = str(data.get("category") or "")
        if not is_builtin:
            # Someone else's theme goes in Custom whatever the file says, so it is
            # always somewhere the user can find it.
            category = USER_CATEGORY
        elif category not in THEME_CATEGORIES:
            # An unknown category has no filter chip, which would leave the theme
            # loaded but unreachable in the gallery.
            logger.info(
                "Theme %r asks for the unknown category %r; filing it under %s",
                name,
                category,
                DEFAULT_CATEGORY,
            )
            category = DEFAULT_CATEGORY
        themes.append(
            {
                "id": name,
                "label": str(data.get("label") or name.replace("-", " ").title()),
                "category": category,
                "description": str(data.get("description") or ""),
                "order": data.get("order") if isinstance(data.get("order"), int) else 10_000,
                "colors": colors,
                # Ours or theirs, and the file it came from - a dropped-in theme can
                # be shown or removed wherever it lives.
                "source": "bundled" if is_builtin else "user",
                "path": path,
            }
        )
    return themes


def _load_all() -> list[dict]:
    """Bundled themes first, then the user's - a user file wins on a name clash."""
    by_id: dict[str, dict] = {}
    for theme in _load_dir(BUNDLED_THEME_DIR, "bundled"):
        by_id[theme["id"]] = theme
    try:
        user_dir = user_theme_dir()
    except Exception:  # pragma: no cover - config dir resolution must not break themes
        user_dir = ""
    if user_dir:
        for theme in _load_dir(user_dir, "user"):
            by_id[theme["id"]] = theme
    return sorted(by_id.values(), key=lambda t: (t["order"], t["label"].lower()))


_THEMES = _load_all()

PALETTES: dict[str, dict] = {t["id"]: t["colors"] for t in _THEMES}
THEME_LABELS: dict[str, str] = {t["id"]: t["label"] for t in _THEMES}
THEME_CATEGORY_MAP: dict[str, str] = {t["id"]: t["category"] for t in _THEMES}
THEME_DESCRIPTIONS: dict[str, str] = {t["id"]: t["description"] for t in _THEMES}
THEME_SOURCES: dict[str, str] = {t["id"]: t["source"] for t in _THEMES}
#: theme id -> the file it was loaded from.
THEME_PATHS: dict[str, str] = {t["id"]: t["path"] for t in _THEMES}


#: Fallback palette, used when a theme name is unknown. Kept as one object for the
#: life of the process so a reload cannot leave a stale reference behind.
DARK: dict[str, str] = dict(PALETTES.get("dark") or next(iter(PALETTES.values()), {}))
if "dark" in PALETTES:
    PALETTES["dark"] = DARK

#: Theme ids in display order. A list rather than a tuple so a reload can update it
#: in place: modules import this name once, and rebinding it would leave them
#: looking at the themes that existed when they were imported.
THEMES: list[str] = list(PALETTES)


def reload_themes() -> None:
    """Re-read the theme files, picking up anything the user has added.

    The dictionaries are updated in place. Other modules hold references to
    `PALETTES` and `DARK` from import time, and rebinding them here would leave
    those pointing at the previous copy.
    """
    global _THEMES
    _THEMES = _load_all()

    for mapping, key in (
        (PALETTES, "colors"),
        (THEME_LABELS, "label"),
        (THEME_CATEGORY_MAP, "category"),
        (THEME_DESCRIPTIONS, "description"),
        (THEME_SOURCES, "source"),
    ):
        mapping.clear()
        mapping.update({theme["id"]: theme[key] for theme in _THEMES})

    THEME_PATHS.clear()
    THEME_PATHS.update({t["id"]: t["path"] for t in _THEMES})

    THEMES[:] = list(PALETTES)
    replacement = PALETTES.get("dark") or (next(iter(PALETTES.values()), {}))
    DARK.clear()
    DARK.update(replacement)
    PALETTES["dark"] = DARK if "dark" in PALETTES else PALETTES.get("dark", DARK)
    _accessible_cache.clear()


def slugify(label: str) -> str:
    """A filename-safe id from a display name."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", label.strip().lower()).strip("-")
    return cleaned or "custom-theme"


def is_user_theme(theme_id: str) -> bool:
    """Whether this theme is the user's rather than one we ship."""
    return theme_id in PALETTES and theme_id not in BUILTIN_THEME_IDS


def user_theme_path(theme_id: str) -> str:
    """The file a theme was loaded from, or where it would be written."""
    known = THEME_PATHS.get(theme_id)
    if known:
        return known
    return os.path.join(user_theme_dir(), f"{theme_id}.json")


def theme_generator(theme_id: str) -> dict | None:
    """The Studio settings a theme was generated from, if it was.

    Themes saved from the Custom Theme Studio record the values that produced
    them, so the Studio can load one back and carry on where it left off.
    Themes we ship, and themes written by hand, have no recipe.
    """
    path = THEME_PATHS.get(theme_id)
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError):
        return None
    recipe = payload.get("generator")
    return dict(recipe) if isinstance(recipe, dict) else None


def save_user_theme(
    label: str,
    colors: dict[str, str],
    generator: dict | None = None,
    theme_id: str | None = None,
    description: str = "",
) -> str:
    """Write a theme to the user's theme directory and return its id.

    A theme saved from the Studio is an ordinary theme file afterwards: it appears
    in the gallery, it can be edited by hand, and it can be sent to someone else.
    """
    theme_id = theme_id or slugify(label)
    if theme_id in BUILTIN_THEME_IDS:
        raise ValueError(f"{theme_id!r} is a built-in theme; choose another name")
    missing = [token for token in REQUIRED_TOKENS if token not in colors]
    if missing:
        raise ValueError(f"Theme is missing {', '.join(sorted(missing))}")

    payload = {
        "id": theme_id,
        "label": label.strip() or theme_id,
        "category": USER_CATEGORY,
        "description": description or "Saved from the Custom Theme Studio",
        "order": 9_000,
        "colors": dict(sorted(colors.items())),
    }
    if generator:
        payload["generator"] = generator

    directory = user_theme_dir()
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{theme_id}.json")
    temp = path + ".tmp"
    with open(temp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(temp, path)

    reload_themes()
    return theme_id


def delete_user_theme(theme_id: str) -> bool:
    """Remove a saved theme. Bundled themes are never touched."""
    if not is_user_theme(theme_id):
        return False
    try:
        os.remove(user_theme_path(theme_id))
    except OSError:
        return False
    reload_themes()
    return True


def user_themes() -> list[str]:
    """Ids of the themes this user saved or dropped in, in display order."""
    return [name for name in PALETTES if is_user_theme(name)]


#: The generated custom palette is cached against the settings that produced it.
_custom_palette_cache: dict = {}


def get_custom_theme_palette(custom_config: dict | None = None) -> dict:
    """Generate and cache the custom palette based on settings or provided config."""
    global _custom_palette_cache
    if custom_config is None:
        try:
            from crapcleaner.config import load_settings

            settings = load_settings()
            custom_config = settings.get("custom_theme", {})
        except Exception:
            custom_config = {}

    primary = custom_config.get("primary_color", "#3b82f6")
    mode = custom_config.get("mode", "dark")
    mood = custom_config.get("mood", "cohesive")
    s_contrast = custom_config.get("surface_contrast", 1.0)
    a_intensity = custom_config.get("accent_intensity", 1.0)
    bg_dark = custom_config.get("bg_darkness", 1.0)

    cache_key = (primary, mode, mood, float(s_contrast), float(a_intensity), float(bg_dark))
    if _custom_palette_cache.get("key") == cache_key and "palette" in _custom_palette_cache:
        return _custom_palette_cache["palette"]

    from crapcleaner.gui.color_engine import generate_custom_palette

    pal = generate_custom_palette(
        primary_color=primary,
        mode=mode,
        surface_contrast=s_contrast,
        accent_intensity=a_intensity,
        bg_darkness=bg_dark,
        mood=mood,
    )
    _custom_palette_cache["key"] = cache_key
    _custom_palette_cache["palette"] = pal
    return pal


def invalidate_custom_theme_cache() -> None:
    """Clear the cached custom palette so the next lookup regenerates it."""
    global _custom_palette_cache
    _custom_palette_cache.clear()


#: Text roles and the backgrounds the stylesheet actually draws them on. Cards use
#: `panel` and switch to `elevated` on hover; tables and headers use `surface` and
#: `surface2`; the window itself uses `window`. Only pairs that really appear
#: together are enforced - checking every colour against every other would flag
#: combinations the interface never renders.
_TEXT_ROLES = ("text", "muted")
_TEXT_BACKGROUNDS = ("window", "panel", "surface", "surface2", "elevated")

#: WCAG 2.1 AA for body text.
MIN_TEXT_CONTRAST = 4.5

#: Palettes that may keep a text colour below AA, with the reason. Nothing is listed
#: today; an entry here is a deliberate, reviewed exception, not a way to silence the
#: test.
CONTRAST_EXEMPTIONS: dict[str, str] = {}

_BADGE_ROLES = ("accent", "success", "warning", "danger", "info", "review")

_accessible_cache: dict[str, dict] = {}


def derive_ink(palette: dict) -> dict:
    """Add the label colours the interface draws but no theme file sets.

    Two of them: the text on a coloured button, and the text on a soft badge.
    Both used to be hard-coded - white on the button, the role's own colour on a
    fifteen-percent tint of itself - and both are unreadable on a good half of the
    themes we ship. Deriving them from what they sit on settles it once, for every
    theme, instead of asking each theme to work around a constant.

    Idempotent: a palette that already carries a token keeps it.
    """
    from crapcleaner.gui.color_engine import ensure_contrast, flatten_alpha

    card = palette.get("surface", "#202020")
    wanted: list[tuple[str, str | None, str | None]] = [
        ("on_accent", palette.get("accent"), "#ffffff"),
        ("on_danger", palette.get("danger"), "#ffffff"),
    ]
    for role in _BADGE_ROLES:
        tint = palette.get(f"{role}_soft")
        wanted.append(
            (
                f"on_{role}_soft",
                flatten_alpha(tint, card) if tint else None,
                palette.get(role),
            )
        )

    derived = None
    for token, behind, ink in wanted:
        if token in palette or not behind or not ink:
            continue
        if derived is None:
            derived = dict(palette)
        derived[token] = ensure_contrast(ink, behind, min_ratio=MIN_TEXT_CONTRAST)
    return derived if derived is not None else palette


def _readable_over(foreground: str, backgrounds: list[str], min_ratio: float) -> str:
    """The nearest lightness to `foreground` that clears every background.

    Correcting against only the worst background is sound while the correction
    can move one way. Once it can move either way, a colour can satisfy the
    background it fared worst on and fail a lighter one.
    """
    from crapcleaner.gui.color_engine import contrast_ratio, hex_to_hsl, hsl_to_hex

    if all(contrast_ratio(foreground, bg) >= min_ratio for bg in backgrounds):
        return foreground

    hue, saturation, lightness = hex_to_hsl(foreground)
    nearest: tuple[float, str] | None = None
    # Some palettes draw text on backgrounds too far apart for any one lightness
    # to clear them all. Rather than leave it unreadable, take whatever reads
    # best - which is what the previous fallback to white amounted to, chosen
    # deliberately instead of by accident.
    fallback: tuple[float, str] | None = None

    def rate(candidate: str) -> float:
        return min(contrast_ratio(candidate, bg) for bg in backgrounds)

    for step in (0.03, -0.03):
        current = lightness
        for _ in range(34):
            current = max(0.02, min(0.98, current + step))
            candidate = hsl_to_hex(hue, saturation, current)
            worst = rate(candidate)
            if fallback is None or worst > fallback[0]:
                fallback = (worst, candidate)
            if worst >= min_ratio:
                distance = abs(current - lightness)
                if nearest is None or distance < nearest[0]:
                    nearest = (distance, candidate)
                break
    for extreme in ("#ffffff", "#0f172a"):
        worst = rate(extreme)
        if fallback is None or worst > fallback[0]:
            fallback = (worst, extreme)

    if nearest is not None:
        return nearest[1]
    return fallback[1] if fallback is not None else foreground


def _with_accessible_text(name: str, palette: dict) -> dict:
    """Raise text colours that fall below AA on a background they are drawn on.

    `color_engine.ensure_contrast` was already applied to generated custom themes
    while the 44 built-in palettes were exempt from it - on `commodore-64`, hovering
    a card left its secondary text at 1.21:1, which is invisible. Only the text
    colour moves: the accent, surfaces and borders that give a palette its identity
    are untouched.
    """
    palette = derive_ink(palette)
    if name in CONTRAST_EXEMPTIONS:
        return palette

    backgrounds = [palette[key] for key in _TEXT_BACKGROUNDS if palette.get(key)]
    if not backgrounds:
        return palette

    adjusted = None
    for role in _TEXT_ROLES:
        foreground = palette.get(role)
        if not foreground:
            continue
        fixed = _readable_over(foreground, backgrounds, MIN_TEXT_CONTRAST)
        if fixed != foreground:
            if adjusted is None:
                adjusted = dict(palette)
            adjusted[role] = fixed
    return adjusted if adjusted is not None else palette


def accessible_palette(name: str, palette: dict) -> dict:
    """Cached :func:`_with_accessible_text`; palettes are static."""
    cached = _accessible_cache.get(name)
    if cached is None:
        cached = _with_accessible_text(name, palette)
        _accessible_cache[name] = cached
    return cached


def palette_for(theme: str) -> dict:
    if theme == "custom":
        # Custom palettes are generated through ensure_contrast already.
        return get_custom_theme_palette()
    return accessible_palette(theme, PALETTES.get(theme, DARK))


def theme_label(theme: str) -> str:
    return THEME_LABELS.get(theme, theme.title())


def get_theme_category(theme: str) -> str:
    return THEME_CATEGORY_MAP.get(theme, "modern-dark")


def get_theme_category_label(theme: str) -> str:
    cat = get_theme_category(theme)
    return THEME_CATEGORIES.get(cat, cat.replace("-", " ").title())


def get_theme_description(theme: str) -> str:
    return THEME_DESCRIPTIONS.get(theme, f"{theme_label(theme)} color scheme")


def is_dark_theme(theme: str) -> bool:
    pal = palette_for(theme)
    hex_color = pal.get("window", "#000000").lstrip("#")
    if len(hex_color) == 6:
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            return lum < 128
        except ValueError:
            pass
    return True


def get_theme_swatches(theme: str) -> list[str]:
    pal = palette_for(theme)
    return [
        pal.get("window", "#000000"),
        pal.get("surface", "#222222"),
        pal.get("accent", "#3b82f6"),
        pal.get("text", "#ffffff"),
        pal.get("success", "#22c55e"),
    ]
