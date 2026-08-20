"""The high-contrast setting applies to the active theme, not to one palette."""

import pytest

from crapcleaner.gui.color_engine import contrast_ratio
from crapcleaner.gui.theme import palettes as theme


@pytest.fixture(autouse=True)
def restore_mode():
    yield
    theme.set_high_contrast(False)


def _pairs(name):
    palette = theme.palette_for(name)
    for role in (*theme._TEXT_ROLES, "faint"):
        for background in theme._TEXT_BACKGROUNDS:
            if palette.get(role) and palette.get(background):
                yield (role, background), contrast_ratio(palette[role], palette[background])


def test_off_by_default_leaves_the_palette_alone():
    theme.set_high_contrast(False)
    assert theme.palette_for("dark") == theme.accessible_palette("dark", theme.PALETTES["dark"])


def test_setting_applies_to_every_theme_not_just_the_high_contrast_one():
    theme.set_high_contrast(False)
    baseline = {name: dict(_pairs(name)) for name in theme.THEMES}
    theme.set_high_contrast(True)
    strict = {name: dict(_pairs(name)) for name in theme.THEMES}

    improved = 0
    for name, pairs in baseline.items():
        for key, before in pairs.items():
            after = strict[name][key]
            assert after >= before - 0.01, f"{name} {key} got worse: {before} -> {after}"
            assert after >= theme.MIN_TEXT_CONTRAST, f"{name} {key} fell below AA: {after}"
            improved += after > before + 0.01
    assert improved, "high contrast changed nothing anywhere"


def test_ordinary_themes_reach_aaa():
    theme.set_high_contrast(True)
    for name in ("dark", "light", "nord", "dracula", "solarized-dark"):
        for key, ratio in _pairs(name):
            assert ratio >= theme.HIGH_CONTRAST_RATIO, f"{name} {key} only {ratio}"


def test_a_palette_too_wide_for_aaa_still_clears_aa():
    """commodore-64's backgrounds span too far for one lightness to clear them all."""
    theme.set_high_contrast(True)
    ratios = [ratio for _key, ratio in _pairs("commodore-64")]
    assert min(ratios) >= theme.MIN_TEXT_CONTRAST
    assert max(ratios) >= theme.HIGH_CONTRAST_RATIO


def test_label_colours_on_accents_are_raised_too():
    theme.set_high_contrast(False)
    before = theme.palette_for("dark")
    theme.set_high_contrast(True)
    after = theme.palette_for("dark")
    assert contrast_ratio(after["on_accent"], after["accent"]) >= contrast_ratio(
        before["on_accent"], before["accent"]
    )


def test_the_flag_is_read_from_settings_when_nobody_published_it():
    from crapcleaner.config import save_settings

    theme._high_contrast_mode = None
    save_settings({"high_contrast": True})
    assert theme.high_contrast() is True
    theme._high_contrast_mode = None
    save_settings({"high_contrast": False})
    assert theme.high_contrast() is False
