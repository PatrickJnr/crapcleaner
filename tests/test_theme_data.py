"""Themes load from data files, so a palette can be contributed without code.

ARCH-06: `gui/theme.py` held 44 palettes and the whole stylesheet in one module.
"""

import json
import os

import pytest

from crapcleaner.gui import theme as theme_module
from crapcleaner.gui.theme import palettes as palettes_module


def _write_theme(directory, name, **overrides):
    payload = {
        "id": name,
        "label": overrides.pop("label", name.title()),
        "category": overrides.pop("category", "modern-dark"),
        "description": overrides.pop("description", ""),
        "order": overrides.pop("order", 500),
        "colors": overrides.pop("colors", dict(palettes_module.PALETTES["dark"])),
    }
    payload.update(overrides)
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{name}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    return path


class TestBundledThemes:
    def test_every_bundled_theme_file_is_loaded(self):
        """Counting palettes would break as soon as a user saves one of their own."""
        import json

        for filename in os.listdir(palettes_module.BUNDLED_THEME_DIR):
            if not filename.endswith(".json"):
                continue
            with open(
                os.path.join(palettes_module.BUNDLED_THEME_DIR, filename), encoding="utf-8"
            ) as fh:
                theme_id = json.load(fh)["id"]
            assert theme_id in palettes_module.PALETTES, f"{filename} did not load"

    def test_every_theme_we_ship_is_present(self):
        for theme_id in palettes_module.BUILTIN_THEME_IDS:
            assert theme_id in palettes_module.PALETTES

    def test_each_file_defines_every_required_colour(self):
        for filename in sorted(os.listdir(palettes_module.BUNDLED_THEME_DIR)):
            if not filename.endswith(".json"):
                continue
            with open(
                os.path.join(palettes_module.BUNDLED_THEME_DIR, filename), encoding="utf-8"
            ) as fh:
                data = json.load(fh)
            missing = set(palettes_module.REQUIRED_TOKENS) - set(data["colors"])
            assert not missing, f"{filename} is missing {sorted(missing)}"

    def test_the_public_names_still_come_from_the_package(self):
        for name in ("PALETTES", "THEMES", "palette_for", "apply_theme", "_build_stylesheet"):
            assert hasattr(theme_module, name), f"{name} is no longer exported"

    def test_a_stylesheet_can_still_be_built_for_every_theme(self):
        for name in theme_module.THEMES:
            assert "QMainWindow" in theme_module._build_stylesheet(theme_module.palette_for(name))

    def test_themes_keep_a_stable_display_order(self):
        assert list(theme_module.THEMES)[0] == "amber-crt"
        assert "dark" in theme_module.THEMES


class TestUserContributedThemes:
    @pytest.fixture
    def user_dir(self, tmp_path, monkeypatch):
        from crapcleaner import config as config_module

        monkeypatch.setattr(config_module, "config_dir", lambda: str(tmp_path))
        directory = str(tmp_path / "themes")
        yield directory
        # Undo the config redirect *before* reloading, or the reload picks the test's
        # themes up again and leaves them in the registry for every later test.
        monkeypatch.undo()
        palettes_module.reload_themes()

    def test_a_dropped_in_file_becomes_a_theme(self, user_dir):
        _write_theme(user_dir, "my-theme", label="My Theme")

        palettes_module.reload_themes()

        assert "my-theme" in palettes_module.PALETTES
        assert palettes_module.THEME_LABELS["my-theme"] == "My Theme"
        assert palettes_module.THEME_SOURCES["my-theme"] == "user"

    def test_a_user_file_overrides_a_bundled_theme_of_the_same_name(self, user_dir):
        colors = dict(palettes_module.PALETTES["dark"])
        colors["accent"] = "#ff00ff"
        _write_theme(user_dir, "dark", colors=colors)

        palettes_module.reload_themes()

        assert palettes_module.PALETTES["dark"]["accent"] == "#ff00ff"

    def test_a_theme_missing_a_colour_is_skipped_not_fatal(self, user_dir):
        incomplete = dict(palettes_module.PALETTES["dark"])
        del incomplete["accent"]
        _write_theme(user_dir, "broken", colors=incomplete)

        palettes_module.reload_themes()

        assert "broken" not in palettes_module.PALETTES
        assert len(palettes_module.PALETTES) >= 44

    def test_a_theme_with_a_bad_colour_value_is_skipped(self, user_dir):
        wrong = dict(palettes_module.PALETTES["dark"])
        wrong["accent"] = "not-a-colour"
        _write_theme(user_dir, "bad-value", colors=wrong)

        palettes_module.reload_themes()

        assert "bad-value" not in palettes_module.PALETTES

    def test_malformed_json_does_not_break_loading(self, user_dir):
        os.makedirs(user_dir, exist_ok=True)
        with open(os.path.join(user_dir, "truncated.json"), "w", encoding="utf-8") as fh:
            fh.write('{"id": "truncated", "colors": {')

        palettes_module.reload_themes()

        assert len(palettes_module.PALETTES) >= 44

    def test_a_user_theme_is_also_held_to_the_contrast_rule(self, user_dir):
        from crapcleaner.gui.color_engine import contrast_ratio

        colors = dict(palettes_module.PALETTES["dark"])
        colors["muted"] = colors["panel"]  # invisible on purpose
        _write_theme(user_dir, "low-contrast", colors=colors)
        palettes_module.reload_themes()

        palette = theme_module.palette_for("low-contrast")

        assert contrast_ratio(palette["muted"], palette["panel"]) >= theme_module.MIN_TEXT_CONTRAST
