"""Regression tests for the 2026-08-19 audit: logging and untested modules.

Finding IDs refer to audit.md.
"""

import logging
import os
from unittest.mock import patch

import pytest


class TestApplicationLogging:
    """ARCH-01: LOG_FILE was declared and never written; 36 handlers ended in `pass`."""

    def _fresh_logging(self, tmp_path, monkeypatch):
        from crapcleaner import config as config_module
        from crapcleaner.utils import logs as logs_module

        monkeypatch.setattr(config_module, "config_dir", lambda: str(tmp_path))
        monkeypatch.setattr(logs_module, "_configured", False)
        root = logging.getLogger("crapcleaner")
        for handler in list(root.handlers):
            root.removeHandler(handler)
        return logs_module

    def test_a_log_file_is_actually_written(self, tmp_path, monkeypatch):
        logs_module = self._fresh_logging(tmp_path, monkeypatch)

        logs_module.configure_logging(verbose=True)
        logs_module.get_logger("test").warning("something worth reporting")

        for handler in logging.getLogger("crapcleaner").handlers:
            handler.flush()
        path = logs_module.log_path()
        assert os.path.exists(path), "nothing was written"
        with open(path, encoding="utf-8") as fh:
            assert "something worth reporting" in fh.read()

    def test_default_level_keeps_debug_chatter_out(self, tmp_path, monkeypatch):
        logs_module = self._fresh_logging(tmp_path, monkeypatch)

        logs_module.configure_logging(verbose=False)
        logs_module.get_logger("test").debug("noisy detail")
        logs_module.get_logger("test").warning("kept")

        for handler in logging.getLogger("crapcleaner").handlers:
            handler.flush()
        with open(logs_module.log_path(), encoding="utf-8") as fh:
            content = fh.read()
        assert "noisy detail" not in content
        assert "kept" in content

    def test_an_unwritable_location_does_not_break_startup(self, tmp_path, monkeypatch):
        from crapcleaner import config as config_module
        from crapcleaner.utils import logs as logs_module

        monkeypatch.setattr(config_module, "config_dir", lambda: str(tmp_path / "nope"))
        monkeypatch.setattr(logs_module, "_configured", False)
        with patch("os.makedirs", side_effect=OSError("read-only")):
            logs_module.configure_logging()  # must not raise

    def test_a_failing_category_provider_is_reported(self, tmp_path, monkeypatch, caplog):
        """ARCH-05: a broken provider removed its whole group with no trace."""
        import crapcleaner.registry as registry

        def broken():
            raise RuntimeError("provider exploded")

        with (
            patch.object(registry, "SIMPLE_PROVIDERS", [("Windows", broken)]),
            caplog.at_level(logging.WARNING, logger="crapcleaner.registry"),
        ):
            categories = registry.get_all_categories()

        assert isinstance(categories, list)  # the other providers still run
        assert any("Windows" in record.message for record in caplog.records)

    def test_the_cli_can_report_where_the_log_lives(self, capsys, tmp_path, monkeypatch):
        from crapcleaner import config as config_module
        from crapcleaner.cli import run

        monkeypatch.setattr(config_module, "config_dir", lambda: str(tmp_path))

        assert run(["--log-path"]) == 0
        assert str(tmp_path) in capsys.readouterr().out


class TestCustomThemeStudio:
    """TEST-02: the largest interactive module had no tests at all."""

    @pytest.fixture
    def builder(self, qt_app, tmp_path, monkeypatch):
        from crapcleaner import config as config_module
        from crapcleaner.gui.custom_theme_builder import CustomThemeBuilderWidget

        monkeypatch.setattr(config_module, "config_dir", lambda: str(tmp_path))
        widget = CustomThemeBuilderWidget()
        yield widget
        widget.deleteLater()

    def test_it_builds_with_default_settings(self, builder):
        assert builder._current_primary.startswith("#")
        assert builder._current_mode in ("dark", "light", "oled")

    def test_setting_a_primary_colour_updates_the_preview(self, builder):
        builder._set_primary_color("#ff0055")

        assert builder._current_primary == "#ff0055"

    def test_an_invalid_hex_is_rejected_rather_than_stored(self, builder):
        before = builder._current_primary

        builder._on_hex_text_changed("not-a-colour")

        assert builder._current_primary == before

    def test_applying_publishes_the_configuration(self, builder):
        """The widget emits the config; the settings view is what stores it."""
        published = []
        builder.theme_applied.connect(published.append)

        builder._set_primary_color("#12ab34")
        builder._set_mode("light")
        builder._apply_and_save()

        assert published, "applying published nothing"
        assert published[-1]["primary_color"] == "#12ab34"
        assert published[-1]["mode"] == "light"

    def test_reset_restores_the_defaults(self, builder):
        builder._set_primary_color("#ff0055")
        builder._set_mode("light")

        builder._reset_to_defaults()

        assert builder._current_primary == "#3b82f6"
        assert builder._current_mode == "dark"

    def test_the_generated_palette_meets_aa(self, builder):
        """The custom generator was already contrast-checked; keep it that way."""
        from crapcleaner.gui.color_engine import contrast_ratio
        from crapcleaner.gui.theme import (
            _TEXT_BACKGROUNDS,
            _TEXT_ROLES,
            MIN_TEXT_CONTRAST,
            get_custom_theme_palette,
            invalidate_custom_theme_cache,
        )

        builder._set_primary_color("#7c3aed")
        builder._apply_and_save()
        invalidate_custom_theme_cache()
        palette = get_custom_theme_palette()

        for role in _TEXT_ROLES:
            for background in _TEXT_BACKGROUNDS:
                if palette.get(role) and palette.get(background):
                    assert (
                        contrast_ratio(palette[role], palette[background]) >= MIN_TEXT_CONTRAST
                    ), f"{role} on {background}"

    def test_a_saved_configuration_is_loaded_back(self, qt_app, tmp_path, monkeypatch):
        from crapcleaner import config as config_module
        from crapcleaner.config import save_settings
        from crapcleaner.gui.custom_theme_builder import CustomThemeBuilderWidget

        monkeypatch.setattr(config_module, "config_dir", lambda: str(tmp_path))
        save_settings({"custom_theme": {"primary_color": "#0abab5", "mode": "light"}})

        widget = CustomThemeBuilderWidget()

        assert widget._current_primary == "#0abab5"
        assert widget._current_mode == "light"
        widget.deleteLater()
