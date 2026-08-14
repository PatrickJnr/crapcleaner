"""Tests for settings persistence."""

from crapcleaner.config.settings import (
    config_dir,
    config_path,
    load_settings,
    save_settings,
    update_settings,
)


class TestSettings:
    def test_defaults_when_missing(self):
        settings = load_settings()
        assert settings["theme"] == "dark"
        assert settings["dry_run_default"] is True
        assert settings["confirm_cleanup"] is True

    def test_save_then_load(self):
        save_settings({"theme": "light", "max_scan_files": 999})
        settings = load_settings()
        assert settings["theme"] == "light"
        assert settings["max_scan_files"] == 999
        # untouched defaults preserved
        assert settings["dry_run_default"] is True

    def test_update_settings(self):
        result = update_settings(dry_run_default=False)
        assert result["dry_run_default"] is False
        assert load_settings()["dry_run_default"] is False

    def test_unknown_keys_ignored(self):
        save_settings({"not_a_real_key": 42})
        settings = load_settings()
        assert "not_a_real_key" not in settings

    def test_corrupt_file_returns_defaults(self, tmp_path):
        config_dir_ = config_dir()
        import os

        os.makedirs(config_dir_, exist_ok=True)
        with open(config_path(), "w", encoding="utf-8") as fh:
            fh.write("{ not json !!!")
        settings = load_settings()
        assert settings["theme"] == "dark"
