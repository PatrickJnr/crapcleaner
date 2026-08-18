"""Tests for settings persistence."""

from crapcleaner.config import (
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


def test_settings_view_tab_navigation_and_controls(app):
    from PySide6.QtCore import Qt

    from crapcleaner.gui.views import SettingsView

    class FakeMain:
        def __init__(self):
            self._settings = {}

        def apply_settings(self):
            pass

        def switch_theme(self, t):
            pass

    fake_main = FakeMain()
    view = SettingsView(fake_main)

    assert view.tab_stack.count() == 7
    assert view.tab_stack.currentIndex() == 0

    # Test tab switching
    view._set_active_tab("custom_studio", 1)
    assert view.tab_stack.currentIndex() == 1
    assert view._section_buttons["custom_studio"].property("active") == "true"
    assert view._section_buttons["themes"].property("active") == "false"

    view._set_active_tab("safety", 2)
    assert view.tab_stack.currentIndex() == 2
    assert view._section_buttons["safety"].property("active") == "true"

    view._set_active_tab("rules", 5)
    assert view.tab_stack.currentIndex() == 5

    # Test category batch selection
    view._disable_all_categories()
    for i in range(view.cat_list.count()):
        assert view.cat_list.item(i).checkState() == Qt.CheckState.Unchecked

    view._enable_all_categories()
    for i in range(view.cat_list.count()):
        assert view.cat_list.item(i).checkState() == Qt.CheckState.Checked

    view._enable_safe_only_categories()
    # At least some categories should be checked (the SAFE ones)
    checked_count = sum(
        1
        for i in range(view.cat_list.count())
        if view.cat_list.item(i).checkState() == Qt.CheckState.Checked
    )
    assert 0 < checked_count < view.cat_list.count()

    # Test apply theme
    view.apply_theme("nord")
    assert view._theme == "nord"
