"""Saved themes are real themes, and editing a theme file takes effect immediately."""

import json
import os

import pytest

from crapcleaner.gui import theme as theme_module
from crapcleaner.gui.color_engine import generate_custom_palette
from crapcleaner.gui.theme import palettes as palettes_module


@pytest.fixture
def theme_home(tmp_path, monkeypatch):
    """Point the user theme directory at a temporary one, and restore it after."""
    from crapcleaner import config as config_module

    monkeypatch.setattr(config_module, "config_dir", lambda: str(tmp_path))
    palettes_module.reload_themes()
    yield str(tmp_path / "themes")
    monkeypatch.undo()
    palettes_module.reload_themes()


class TestSavingAThemeFromTheStudio:
    def test_a_saved_theme_joins_the_gallery(self, theme_home):
        colors = dict(palettes_module.PALETTES["dark"])
        colors["accent"] = "#ff2266"

        theme_id = theme_module.save_user_theme("Hot Pink", colors)

        assert theme_id == "hot-pink"
        assert theme_id in theme_module.THEMES
        assert theme_module.theme_label(theme_id) == "Hot Pink"
        assert theme_module.palette_for(theme_id)["accent"] == "#ff2266"

    def test_it_is_filed_under_custom(self, theme_home):
        theme_module.save_user_theme("Mine", dict(palettes_module.PALETTES["dark"]))

        assert theme_module.get_theme_category("mine") == "custom"
        assert theme_module.is_user_theme("mine") is True
        assert theme_module.is_user_theme("dark") is False

    def test_a_built_in_name_cannot_be_taken(self, theme_home):
        with pytest.raises(ValueError):
            theme_module.save_user_theme("Dracula", dict(palettes_module.PALETTES["dark"]))

    def test_saving_again_replaces_rather_than_duplicates(self, theme_home):
        colors = dict(palettes_module.PALETTES["dark"])
        theme_module.save_user_theme("Twice", colors)
        colors["accent"] = "#00ff00"
        theme_module.save_user_theme("Twice", colors)

        assert [t for t in theme_module.THEMES if t == "twice"] == ["twice"]
        assert theme_module.palette_for("twice")["accent"] == "#00ff00"

    def test_an_incomplete_palette_is_refused(self, theme_home):
        broken = dict(palettes_module.PALETTES["dark"])
        del broken["accent"]

        with pytest.raises(ValueError):
            theme_module.save_user_theme("Broken", broken)

    def test_a_saved_theme_can_be_deleted(self, theme_home):
        theme_module.save_user_theme("Temporary", dict(palettes_module.PALETTES["dark"]))

        assert theme_module.delete_user_theme("temporary") is True
        assert "temporary" not in theme_module.THEMES

    def test_a_bundled_theme_cannot_be_deleted(self, theme_home):
        assert theme_module.delete_user_theme("dark") is False
        assert "dark" in theme_module.THEMES

    def test_a_saved_theme_still_meets_the_contrast_rule(self, theme_home):
        from crapcleaner.gui.color_engine import contrast_ratio

        colors = dict(palettes_module.PALETTES["dark"])
        colors["muted"] = colors["panel"]
        theme_module.save_user_theme("Unreadable", colors)

        palette = theme_module.palette_for("unreadable")

        assert contrast_ratio(palette["muted"], palette["panel"]) >= theme_module.MIN_TEXT_CONTRAST


class TestEditingAThemeFile:
    def test_an_edit_is_picked_up_by_a_reload(self, theme_home):
        theme_id = theme_module.save_user_theme("Editable", dict(palettes_module.PALETTES["dark"]))
        path = theme_module.user_theme_path(theme_id)

        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        data["colors"]["accent"] = "#123456"
        data["label"] = "Edited By Hand"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

        palettes_module.reload_themes()

        assert theme_module.palette_for(theme_id)["accent"] == "#123456"
        assert theme_module.theme_label(theme_id) == "Edited By Hand"

    def test_a_theme_deleted_on_disk_disappears(self, theme_home):
        theme_id = theme_module.save_user_theme("Gone", dict(palettes_module.PALETTES["dark"]))
        os.remove(theme_module.user_theme_path(theme_id))

        palettes_module.reload_themes()

        assert theme_id not in theme_module.THEMES

    def test_a_broken_edit_leaves_the_other_themes_alone(self, theme_home):
        theme_id = theme_module.save_user_theme("Fragile", dict(palettes_module.PALETTES["dark"]))
        with open(theme_module.user_theme_path(theme_id), "w", encoding="utf-8") as fh:
            fh.write("{ not json")

        palettes_module.reload_themes()

        assert theme_id not in theme_module.THEMES
        assert "dark" in theme_module.THEMES

    def test_a_theme_we_did_not_ship_lands_in_custom(self, theme_home):
        """Whatever the file claims, someone else's theme belongs in Custom."""
        os.makedirs(theme_home, exist_ok=True)
        payload = {
            "id": "odd",
            "label": "Odd",
            "category": "not-a-real-category",
            "colors": dict(palettes_module.PALETTES["dark"]),
        }
        with open(os.path.join(theme_home, "odd.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

        palettes_module.reload_themes()

        assert theme_module.get_theme_category("odd") == "custom"
        assert theme_module.is_user_theme("odd") is True

    def test_references_survive_a_reload(self, theme_home):
        """Modules import PALETTES once; a reload must not orphan those references."""
        palettes_before = theme_module.PALETTES
        dark_before = theme_module.DARK

        theme_module.save_user_theme("Another", dict(palettes_module.PALETTES["dark"]))

        assert theme_module.PALETTES is palettes_before
        assert theme_module.DARK is dark_before
        assert "another" in palettes_before


class TestTheWatcher:
    def test_it_watches_the_user_theme_directory(self, qt_app, theme_home):
        from crapcleaner.gui.theme_watcher import ThemeWatcher

        watcher = ThemeWatcher()
        try:
            assert os.path.isdir(theme_home), "the watcher should create the directory"
            watched = watcher._watcher.directories()
            assert theme_home in watched
            # A theme dropped in beside the shipped ones must reload too.
            assert palettes_module.BUNDLED_THEME_DIR in watched
        finally:
            watcher.stop()

    def test_a_new_file_is_watched_after_a_reload(self, qt_app, theme_home):
        from crapcleaner.gui.theme_watcher import ThemeWatcher

        watcher = ThemeWatcher()
        try:
            theme_module.save_user_theme("Watched", dict(palettes_module.PALETTES["dark"]))
            watcher.rewatch()

            assert theme_module.user_theme_path("watched") in watcher._watcher.files()
        finally:
            watcher.stop()

    def test_a_change_reloads_and_announces_it(self, qt_app, theme_home):
        from crapcleaner.gui.theme_watcher import ThemeWatcher

        theme_id = theme_module.save_user_theme("Signalled", dict(palettes_module.PALETTES["dark"]))
        watcher = ThemeWatcher()
        announced = []
        watcher.themes_changed.connect(lambda: announced.append(True))
        try:
            path = theme_module.user_theme_path(theme_id)
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            data["colors"]["accent"] = "#abcdef"
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)

            # Drive the debounce directly rather than waiting on the filesystem.
            watcher._reload()

            assert announced == [True]
            assert theme_module.palette_for(theme_id)["accent"] == "#abcdef"
        finally:
            watcher.stop()

    def test_a_broken_file_does_not_take_the_watcher_down(self, qt_app, theme_home):
        from crapcleaner.gui.theme_watcher import ThemeWatcher

        watcher = ThemeWatcher()
        try:
            os.makedirs(theme_home, exist_ok=True)
            with open(os.path.join(theme_home, "bad.json"), "w", encoding="utf-8") as fh:
                fh.write("{{{")

            watcher._reload()  # must not raise

            assert "dark" in theme_module.THEMES
        finally:
            watcher.stop()


class TestProvenance:
    """Membership of the shipped list decides whose theme it is."""

    def test_every_listed_theme_exists(self):
        import os

        for theme_id in theme_module.BUILTIN_THEME_IDS:
            path = os.path.join(palettes_module.BUNDLED_THEME_DIR, f"{theme_id}.json")
            assert os.path.isfile(path), f"{theme_id} is listed but not shipped"

    def test_the_shipped_themes_are_not_treated_as_the_users(self):
        for theme_id in ("dark", "dracula", "custom"):
            assert theme_module.is_user_theme(theme_id) is False

    def test_a_file_beside_the_shipped_ones_is_still_the_users(self, theme_home):
        import json
        import os

        payload = {
            "id": "dropped-in",
            "label": "Dropped In",
            "category": "modern-dark",
            "colors": dict(palettes_module.PALETTES["dark"]),
        }
        path = os.path.join(palettes_module.BUNDLED_THEME_DIR, "dropped-in.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        try:
            palettes_module.reload_themes()

            assert theme_module.is_user_theme("dropped-in") is True
            assert theme_module.get_theme_category("dropped-in") == "custom"
            # Removable from the gallery even though it is not in the user's dir.
            assert theme_module.user_theme_path("dropped-in") == path
        finally:
            if os.path.exists(path):
                os.remove(path)
            palettes_module.reload_themes()


class TestReloadKeepsTheActiveTheme:
    """A theme file changing must not swap the window to a different theme.

    `MainWindow._settings` is the snapshot taken at start-up and is not updated when
    the theme is switched, so reloading used to reapply whatever was stored when the
    window opened - Custom, for anyone who had used the Studio - instead of the theme
    actually in use.
    """

    def _window(self, active: str, stored: str):
        from unittest.mock import patch

        from crapcleaner.gui.app import MainWindow

        window = MainWindow.__new__(MainWindow)
        window._theme = active
        window._settings = {"theme": stored}
        window._views = {}
        applied = []
        from crapcleaner.gui import app as app_module

        with patch.object(MainWindow, "_apply_theme_to_views", lambda self, t: applied.append(t)):
            with patch.object(MainWindow, "statusBar", create=True):
                with patch.object(app_module, "apply_theme", lambda *a, **k: None):
                    MainWindow._on_themes_changed(window)
        return applied

    def test_the_active_theme_is_reapplied_not_the_stored_one(self, qt_app, theme_home):
        applied = self._window(active="analog-horror", stored="custom")

        assert applied == ["analog-horror"], "the reload changed the theme out from under the user"

    def test_a_theme_that_vanished_falls_back_to_dark(self, qt_app, theme_home, monkeypatch):
        from crapcleaner.gui import app as app_module

        monkeypatch.setattr(app_module, "update_settings", lambda **kwargs: dict(kwargs))

        applied = self._window(active="deleted-theme", stored="dark")

        assert applied == ["dark"]

    def test_the_custom_theme_survives_a_reload(self, qt_app, theme_home):
        """ "custom" is generated rather than loaded from a file, so it is always valid."""
        applied = self._window(active="custom", stored="dark")

        assert applied == ["custom"]


class TestGalleryRefresh:
    def test_the_gallery_shows_a_theme_saved_after_it_was_built(self, qt_app, theme_home):
        from crapcleaner.gui.theme_picker import ThemeGalleryWidget

        gallery = ThemeGalleryWidget("dark")
        assert "late-addition" not in gallery._cards

        theme_module.save_user_theme("Late Addition", dict(palettes_module.PALETTES["dark"]))
        gallery.refresh_themes()

        assert "late-addition" in gallery._cards
        assert gallery.theme_combo.findData("late-addition") >= 0
        gallery.deleteLater()

    def test_a_deleted_theme_leaves_the_gallery(self, qt_app, theme_home):
        from crapcleaner.gui.theme_picker import ThemeGalleryWidget

        theme_module.save_user_theme("Short Lived", dict(palettes_module.PALETTES["dark"]))
        gallery = ThemeGalleryWidget("dark")
        assert "short-lived" in gallery._cards

        theme_module.delete_user_theme("short-lived")
        gallery.refresh_themes()

        assert "short-lived" not in gallery._cards
        gallery.deleteLater()

    def test_the_active_theme_falls_back_when_its_file_goes(self, qt_app, theme_home):
        from crapcleaner.gui.theme_picker import ThemeGalleryWidget

        theme_module.save_user_theme("Doomed", dict(palettes_module.PALETTES["dark"]))
        gallery = ThemeGalleryWidget("doomed")
        assert gallery.current_theme() == "doomed"

        theme_module.delete_user_theme("doomed")
        gallery.refresh_themes()

        assert gallery.current_theme() == "dark"
        gallery.deleteLater()

    def test_the_category_counts_follow_the_registry(self, qt_app, theme_home):
        from crapcleaner.gui.theme import THEME_CATEGORIES, get_theme_category
        from crapcleaner.gui.theme_picker import ThemeGalleryWidget

        gallery = ThemeGalleryWidget("dark")
        theme_module.save_user_theme("Counted", dict(palettes_module.PALETTES["dark"]))
        gallery.refresh_themes()

        chips = [b.text().replace("&&", "&") for b in gallery.chip_group.buttons()]
        label = THEME_CATEGORIES["custom"]
        expected = sum(1 for t in theme_module.THEMES if get_theme_category(t) == "custom")
        assert f"{label} ({expected})" in chips
        gallery.deleteLater()


class TestStudioRoundTrip:
    def test_saving_publishes_the_new_theme_id(self, qt_app, theme_home, monkeypatch):
        from crapcleaner.gui.custom_theme_builder import CustomThemeBuilderWidget

        widget = CustomThemeBuilderWidget()
        try:
            monkeypatch.setattr(
                "PySide6.QtWidgets.QInputDialog.getText", lambda *a, **k: ("Studio Save", True)
            )
            published = []
            widget.theme_saved.connect(published.append)

            widget._save_to_gallery()

            assert published == ["studio-save"]
            assert "studio-save" in theme_module.THEMES
            assert theme_module.is_user_theme("studio-save")
        finally:
            widget.deleteLater()


class TestWindowGeometry:
    """The dashboard has a size it was laid out for; the floor has to fit a laptop."""

    def test_the_default_is_the_designed_size(self, qt_app):
        from crapcleaner.gui.app import MainWindow

        assert MainWindow.DEFAULT_SIZE == (1460, 1160)

    def test_the_floor_fits_the_smallest_screen_worth_supporting(self, qt_app):
        from crapcleaner.gui.app import MainWindow

        minimum_width, minimum_height = MainWindow.MINIMUM_SIZE
        # 1280x720 with a 40px taskbar is the smallest realistic desktop.
        assert minimum_width <= 1280
        assert minimum_height <= 680

    def test_the_window_never_opens_larger_than_the_screen(self, qt_app):
        from PySide6.QtWidgets import QApplication

        from crapcleaner.gui.app import MainWindow

        window = MainWindow()
        try:
            screen = window.screen() or QApplication.primaryScreen()
            available = screen.availableGeometry()
            assert window.width() <= max(available.width(), MainWindow.MINIMUM_SIZE[0])
            assert window.height() <= max(available.height(), MainWindow.MINIMUM_SIZE[1])
        finally:
            window.close()


class TestScheduleInSettings:
    """The schedule could be set up from the command line and nowhere else."""

    @pytest.fixture
    def settings_view(self, qt_app, tmp_path, monkeypatch):
        from crapcleaner import config as config_module
        from crapcleaner.gui.views.settings import SettingsView

        monkeypatch.setattr(config_module, "config_dir", lambda: str(tmp_path))
        view = SettingsView(None)
        yield view
        view.deleteLater()

    def test_the_section_reports_what_is_registered(self, settings_view):
        assert settings_view.schedule_status_label.text()
        assert settings_view.schedule_last_label.text()

    def test_removing_is_offered_only_when_something_is_scheduled(self, settings_view):
        from unittest.mock import patch

        from crapcleaner.core.scheduler import ScheduleConfig, ScheduleStatus

        registered = ScheduleStatus(
            supported=True,
            registered=True,
            detail="a scheduled task",
            config=ScheduleConfig(enabled=True, at="07:30", frequency="weekly"),
        )
        with patch("crapcleaner.core.scheduler.status", return_value=registered):
            settings_view._refresh_schedule_state()

        assert settings_view.schedule_disable_btn.isEnabled() is True
        assert settings_view.schedule_time.time().toString("HH:mm") == "07:30"
        assert settings_view.schedule_frequency.currentData() == "weekly"

    def test_an_unsupported_platform_disables_the_controls(self, settings_view):
        from unittest.mock import patch

        from crapcleaner.core.scheduler import ScheduleConfig, ScheduleStatus

        unsupported = ScheduleStatus(
            supported=False,
            registered=False,
            detail="Scheduling needs systemctl, which is not available here.",
            config=ScheduleConfig(),
        )
        with patch("crapcleaner.core.scheduler.status", return_value=unsupported):
            settings_view._refresh_schedule_state()

        assert settings_view.schedule_enable_btn.isEnabled() is False
        assert "not available" in settings_view.schedule_status_label.text()

    def test_enabling_passes_what_the_form_says(self, settings_view):
        from unittest.mock import patch

        from PySide6.QtCore import QTime

        settings_view.schedule_time.setTime(QTime(6, 15))
        settings_view.schedule_frequency.setCurrentIndex(1)
        settings_view.schedule_threshold.setValue(2048)

        with patch("crapcleaner.core.scheduler.enable", return_value=(True, "ok")) as enable:
            with patch("PySide6.QtWidgets.QMessageBox.information"):
                settings_view._enable_schedule()

        config = enable.call_args[0][0]
        assert config.at == "06:15"
        assert config.frequency == "weekly"
        assert config.threshold_mb == 2048


class TestStudioControls:
    """The Studio exposes every value a saved theme carries."""

    @pytest.fixture
    def studio(self, qt_app, tmp_path, monkeypatch):
        from crapcleaner import config as config_module
        from crapcleaner.gui.custom_theme_builder import CustomThemeBuilderWidget

        monkeypatch.setattr(config_module, "config_dir", lambda: str(tmp_path))
        widget = CustomThemeBuilderWidget()
        yield widget
        widget.deleteLater()

    def test_background_depth_can_be_changed(self, studio):
        """It is part of every saved theme and had no control at all."""
        studio._on_darkness_changed(70)

        assert studio._current_bg_darkness == 0.7
        assert studio.darkness_val_lbl.text() == "70%"
        assert studio.current_config()["bg_darkness"] == 0.7

    def test_reset_restores_every_slider(self, studio):
        studio._on_darkness_changed(60)
        studio._on_contrast_changed(120)

        studio._reset_to_defaults()

        assert studio._current_bg_darkness == 1.0
        assert studio._current_contrast == 1.0

    def test_the_controls_are_named_for_a_screen_reader(self, studio):
        for slider in (studio.contrast_slider, studio.intensity_slider, studio.darkness_slider):
            assert slider.accessibleName()
        assert all(button.accessibleName() for button in studio._preset_buttons)
        assert all(button.accessibleName() for button in studio._mood_buttons.values())

    def test_the_preview_gets_the_space(self, studio):
        studio.resize(1200, 900)
        studio.show()

        assert studio.preview_card.height() > 400, "the preview is still squashed"


class TestStudioStartFrom:
    """The Studio could only ever build a theme from nothing."""

    @pytest.fixture
    def studio(self, qt_app, theme_home):
        from crapcleaner.gui.custom_theme_builder import CustomThemeBuilderWidget

        widget = CustomThemeBuilderWidget()
        yield widget
        widget.deleteLater()

    def test_a_saved_theme_comes_back_exactly(self, studio, monkeypatch):
        studio._current_primary = "#c04ae0"
        studio._current_mood = "vibrant"
        studio._current_contrast = 1.15
        studio._current_intensity = 0.9
        studio._current_bg_darkness = 1.07
        saved = dict(studio.current_config())
        monkeypatch.setattr(
            "PySide6.QtWidgets.QInputDialog.getText", lambda *a, **k: ("Round Trip", True)
        )
        studio._save_to_gallery()
        studio._reset_to_defaults()
        assert studio.current_config() != saved

        assert studio.load_theme("round-trip") is True
        assert studio.current_config() == saved

    def test_a_saved_theme_joins_the_list_without_reopening_the_page(self, studio, monkeypatch):
        monkeypatch.setattr(
            "PySide6.QtWidgets.QInputDialog.getText", lambda *a, **k: ("Fresh Save", True)
        )

        studio._save_to_gallery()

        assert studio.start_from.findData("fresh-save") >= 0

    def test_a_shipped_theme_is_a_starting_point_and_says_so(self, studio):
        """It has no recipe, so it cannot be reproduced - claiming otherwise would lie."""
        exact = studio.load_theme("dracula")

        assert exact is False
        assert studio._current_primary == theme_module.PALETTES["dracula"]["accent"].lower()
        assert "not a copy" in studio.start_note.text()

    def test_an_unknown_theme_changes_nothing(self, studio):
        before = studio.current_config()

        assert studio.load_theme("no-such-theme") is False
        assert studio.current_config() == before


class TestStudioReadability:
    """A theme is only worth saving if its text can be read."""

    @pytest.fixture
    def studio(self, qt_app, tmp_path, monkeypatch):
        from crapcleaner import config as config_module
        from crapcleaner.gui.custom_theme_builder import CustomThemeBuilderWidget

        monkeypatch.setattr(config_module, "config_dir", lambda: str(tmp_path))
        widget = CustomThemeBuilderWidget()
        yield widget
        widget.deleteLater()

    def test_translucent_badges_are_measured_against_what_is_behind_them(self):
        """rgba() compared with its own accent reads about 1:1 for every theme."""
        from crapcleaner.gui.color_engine import contrast_ratio, flatten_alpha

        accent = "#4783e5"
        soft = "rgba(71, 131, 229, 0.16)"

        assert contrast_ratio(accent, soft) < 1.1, "the bug this guards against"
        over_card = flatten_alpha(soft, "#21252a")
        assert over_card == "#273448"
        assert contrast_ratio(accent, over_card) > 3.0

    def test_a_solid_colour_passes_straight_through(self):
        from crapcleaner.gui.color_engine import flatten_alpha

        assert flatten_alpha("#AABBCC", "#000000") == "#aabbcc"
        assert flatten_alpha("rgb(255, 0, 0)", "#ffffff") == "#ff0000"

    def test_every_rendered_pair_is_reported(self, studio):
        """It is beside the controls, not behind a tab: it is why you would look."""
        from crapcleaner.gui.custom_theme_builder import CONTRAST_PAIRS

        assert len(studio.contrast_rows) == len(CONTRAST_PAIRS)
        assert all(row.text() for row in studio.contrast_rows)
        assert ":1" in studio.contrast_rows[0].text()
        assert studio.contrast_summary.text()

    def test_an_unreadable_pair_is_named_rather_than_averaged_away(self):
        """A failing pair is named and ranked, not folded into an average."""
        from crapcleaner.gui.custom_theme_builder import contrast_report

        blind = dict.fromkeys(
            (
                "window",
                "surface",
                "elevated",
                "text",
                "muted",
                "accent",
                "on_accent",
                "on_accent_soft",
                "accent_soft",
                "success",
                "on_success_soft",
                "success_soft",
                "warning",
                "on_warning_soft",
                "warning_soft",
                "danger",
                "on_danger",
                "on_danger_soft",
                "danger_soft",
            ),
            "#3a3a3a",
        )

        report = contrast_report(blind)

        assert report, "a palette was rated as having no pairs at all"
        assert all(grade == "FAILS" for _, _, grade in report)
        assert all(label for label, _, _ in report), "a failure with no name is unactionable"

    def test_a_generated_palette_passes_every_pair(self, studio):
        """The knobs cannot fix the button and badge labels, so the palette does."""
        studio._set_primary_color("#3b82f6")

        assert studio.preview_card.contrast_failures() == []
        assert "AAA" in studio.preview_card.cr_badge.text() or "AA" in (
            studio.preview_card.cr_badge.text()
        )


class TestStudioAppliesToTheWholeWindow:
    """The interface follows the edit, a moment after the last change."""

    @pytest.fixture
    def studio(self, qt_app, tmp_path, monkeypatch):
        from crapcleaner import config as config_module
        from crapcleaner.gui.custom_theme_builder import CustomThemeBuilderWidget

        monkeypatch.setattr(config_module, "config_dir", lambda: str(tmp_path))
        widget = CustomThemeBuilderWidget()
        yield widget
        widget.deleteLater()

    def test_it_is_on_by_default(self, studio):
        assert studio.live_apply_check.isChecked()

    def test_an_edit_does_not_restyle_the_window_immediately(self, studio):
        """Restyling costs ~240ms, so it waits for the change to settle."""
        applied = []
        studio.theme_applied.connect(applied.append)

        studio._set_primary_color("#00ff88")

        assert applied == [], "restyled the window mid-gesture"
        assert studio._debounce_timer.isActive()

    def test_a_gesture_restyles_the_window_once(self, studio):
        applied = []
        studio.theme_applied.connect(applied.append)

        for colour in ("#00ff88", "#ff0088", "#8800ff", "#ffaa00"):
            studio._set_primary_color(colour)
        studio._apply_debounced()

        assert len(applied) == 1, f"{len(applied)} restyles for one gesture"
        assert applied[0]["primary_color"] == "#ffaa00"

    def test_a_drag_restyles_the_window_once(self, studio):
        applied = []
        studio.theme_applied.connect(applied.append)

        for value in range(50, 140):
            studio._on_darkness_changed(value)
        studio._apply_debounced()

        assert len(applied) == 1
        assert applied[0]["bg_darkness"] == 1.39

    def test_turning_it_off_leaves_the_window_alone(self, studio):
        applied = []
        studio.theme_applied.connect(applied.append)
        studio.live_apply_check.setChecked(False)

        studio._set_primary_color("#00ff88")
        studio._apply_debounced()

        assert applied == []

    def test_the_apply_button_applies_either_way(self, studio):
        applied = []
        studio.theme_applied.connect(applied.append)
        studio.live_apply_check.setChecked(False)

        studio._apply_and_save()

        assert len(applied) == 1

    def test_the_dice_rolls_the_depth_it_returns(self, studio, monkeypatch):
        """It was returned and thrown away, so the roll never matched its own recipe."""
        from crapcleaner.gui import custom_theme_builder as builder_module

        monkeypatch.setattr(
            builder_module,
            "generate_magic_palette",
            lambda: {
                "primary_color": "#123456",
                "mode": "dark",
                "mood": "muted",
                "surface_contrast": 1.1,
                "accent_intensity": 0.8,
                "bg_darkness": 1.2,
            },
        )

        studio._on_magic_dice_clicked()

        assert studio._current_bg_darkness == 1.2
        assert studio.darkness_slider.value() == 120
        assert studio.contrast_slider.value() == 110
        assert studio.hex_input.text() == "#123456"

    def test_typing_something_that_is_not_a_colour_says_so(self, studio):
        studio._on_hex_text_changed("nonsense")

        assert studio.hex_input.styleSheet(), "no sign that the value was rejected"

        studio._on_hex_text_changed("#3b82f6")

        assert not studio.hex_input.styleSheet()


class TestStudioFillsThePage:
    def test_the_settings_page_gives_the_studio_its_height(self, qt_app, tmp_path, monkeypatch):
        """A trailing stretch left the bottom half of the page empty."""
        from crapcleaner import config as config_module
        from crapcleaner.gui.views.settings import SettingsView

        monkeypatch.setattr(config_module, "config_dir", lambda: str(tmp_path))
        view = SettingsView({}, None)
        try:
            view.resize(1460, 1000)
            view.show()
            view.tab_stack.setCurrentIndex(1)
            qt_app.processEvents()

            page = view.tab_stack.height()
            assert view.custom_builder.height() > page * 0.9, (
                f"{page - view.custom_builder.height()}px of the page is unused"
            )
        finally:
            view.deleteLater()


class TestLabelColoursAreDerived:
    """The interface drew colours no theme set and no control governed."""

    def test_a_pale_accent_does_not_get_a_white_label(self):
        """Every theme drew #ffffff on the primary button whatever colour it was."""
        from crapcleaner.gui.color_engine import contrast_ratio, generate_custom_palette

        palette = generate_custom_palette(
            primary_color="#e8eef7",
            mode="dark",
            mood="cohesive",
            surface_contrast=1.0,
            accent_intensity=1.0,
            bg_darkness=1.0,
        )

        assert palette["on_accent"] != "#ffffff"
        assert contrast_ratio(palette["on_accent"], palette["accent"]) >= 4.5

    def test_every_shipped_theme_has_a_readable_button_label(self):
        from crapcleaner.gui.color_engine import contrast_ratio

        for name in sorted(theme_module.BUILTIN_THEME_IDS):
            palette = theme_module.palette_for(name)
            for ink, behind in (("on_accent", "accent"), ("on_danger", "danger")):
                ratio = contrast_ratio(palette[ink], palette[behind])
                assert ratio >= 4.5, f"{name}: {ink} on {behind} is {ratio:.2f}:1"

    def test_every_shipped_theme_has_a_readable_badge_label(self):
        """A role drawn on a 15% tint of itself is pale on pale."""
        from crapcleaner.gui.color_engine import contrast_ratio, flatten_alpha

        for name in sorted(theme_module.BUILTIN_THEME_IDS):
            palette = theme_module.palette_for(name)
            for role in ("accent", "success", "warning", "danger", "info", "review"):
                tint = flatten_alpha(palette[f"{role}_soft"], palette["surface"])
                ratio = contrast_ratio(palette[f"on_{role}_soft"], tint)
                assert ratio >= 4.5, f"{name}: {role} badge is {ratio:.2f}:1"

    def test_a_raw_palette_can_still_be_styled(self):
        """_build_stylesheet is handed registry palettes as well as prepared ones."""
        from crapcleaner.gui.theme import _build_stylesheet

        css = _build_stylesheet(dict(theme_module.PALETTES["dark"]))

        assert theme_module.PALETTES["dark"]["window"] in css

    def test_deriving_twice_changes_nothing(self):
        once = theme_module.derive_ink(dict(theme_module.PALETTES["dark"]))

        assert theme_module.derive_ink(dict(once)) == once


class TestContrastSearch:
    def test_it_tries_both_directions(self):
        """#3b82f6 sits just inside "dark", so white could only be lightened."""
        from crapcleaner.gui.color_engine import contrast_ratio, ensure_contrast

        fixed = ensure_contrast("#ffffff", "#3b82f6", min_ratio=4.5)

        assert fixed != "#ffffff", "gave up and returned the failing colour"
        assert contrast_ratio(fixed, "#3b82f6") >= 4.5

    def test_text_clears_every_background_not_just_the_worst(self):
        """Correcting against one background can break a lighter one."""
        from crapcleaner.gui.color_engine import contrast_ratio

        for name in sorted(theme_module.BUILTIN_THEME_IDS):
            palette = theme_module.palette_for(name)
            for role in ("text", "muted"):
                for key in ("window", "panel", "surface", "surface2", "elevated"):
                    ratio = contrast_ratio(palette[role], palette[key])
                    assert ratio >= 4.5, f"{name}: {role} on {key} is {ratio:.2f}:1"


class TestReadabilityFix:
    """Reporting a problem without moving it is half a feature."""

    @pytest.fixture
    def studio(self, qt_app, tmp_path, monkeypatch):
        from crapcleaner import config as config_module
        from crapcleaner.gui.custom_theme_builder import CustomThemeBuilderWidget

        monkeypatch.setattr(config_module, "config_dir", lambda: str(tmp_path))
        widget = CustomThemeBuilderWidget()
        yield widget
        widget.deleteLater()

    def test_it_is_only_offered_when_there_is_something_to_fix(self, studio):
        studio._set_primary_color("#3b82f6")

        assert not studio.fix_btn.isEnabled()

    def test_it_reduces_the_failures_it_is_offered_for(self):
        from crapcleaner.gui.custom_theme_builder import _failing_pairs, plan_readability_fix

        broken = {
            "primary_color": "#3b82f6",
            "mode": "dark",
            "mood": "cohesive",
            "surface_contrast": 1.0,
            "accent_intensity": 1.0,
            "bg_darkness": 0.5,
        }
        before = _failing_pairs(broken)
        assert before, "pick a configuration that actually fails"

        fixed, notes = plan_readability_fix(broken)

        assert notes, "changed nothing and said nothing"
        assert _failing_pairs(fixed) == 0

    def test_it_lowers_a_setting_when_that_is_the_answer(self):
        """It only ever offered more Surface Contrast, and the fix here is less.

        On this palette 4,160 slider combinations clear every pair and the
        one-knob-at-a-time search found none of them.
        """
        from crapcleaner.gui.custom_theme_builder import _failing_pairs, plan_readability_fix

        config = {
            "primary_color": "#ec4899",
            "mode": "dark",
            "mood": "pastel",
            "surface_contrast": 1.40,
            "accent_intensity": 1.50,
            "bg_darkness": 0.51,
        }
        assert _failing_pairs(config) == 1

        fixed, notes = plan_readability_fix(config)

        assert _failing_pairs(fixed) == 0
        assert fixed["surface_contrast"] < config["surface_contrast"]
        assert notes

    def test_it_leaves_the_accent_alone(self):
        """The accent is the design; the sliders are the tuning."""
        from crapcleaner.gui.custom_theme_builder import plan_readability_fix

        config = {
            "primary_color": "#ec4899",
            "mode": "dark",
            "mood": "pastel",
            "surface_contrast": 1.40,
            "accent_intensity": 1.50,
            "bg_darkness": 0.51,
        }

        fixed, _ = plan_readability_fix(config)

        assert fixed["primary_color"] == config["primary_color"]
        assert fixed["mode"] == config["mode"]
        assert fixed["mood"] == config["mood"]

    def test_it_never_makes_a_theme_worse(self):
        """Every knob it turns is judged on the whole report, not one pair."""
        import itertools

        from crapcleaner.gui.custom_theme_builder import _failing_pairs, plan_readability_fix

        for primary, mode, mood in itertools.product(
            ("#3b82f6", "#f5d76e", "#111318", "#ec4899"),
            ("dark", "light"),
            ("cohesive", "vibrant", "oled"),
        ):
            config = {
                "primary_color": primary,
                "mode": mode,
                "mood": mood,
                "surface_contrast": 1.0,
                "accent_intensity": 1.0,
                "bg_darkness": 1.0,
            }
            fixed, _ = plan_readability_fix(config)
            assert _failing_pairs(fixed) <= _failing_pairs(config), config

    def test_it_says_what_it_changed(self, studio):
        studio._current_bg_darkness = 0.5
        studio._update_preview(auto_apply=False)
        before = studio.current_config()
        assert studio.fix_btn.isEnabled(), "nothing to fix; pick another configuration"

        studio._fix_readability()

        assert not studio.fix_note.isHidden()
        assert studio.fix_note.text().startswith("Fixed:")
        assert studio.current_config() != before

    def test_what_it_changed_can_be_undone(self, studio):
        studio._current_bg_darkness = 0.5
        studio._update_preview(auto_apply=False)
        studio._fix_readability()

        studio._reset_to_defaults()

        assert studio.current_config()["surface_contrast"] == 1.0
        assert studio.current_config()["accent_intensity"] == 1.0
        assert studio.current_config()["bg_darkness"] == 1.0


class TestStudioStaysResponsive:
    """A slider drag ran the whole update per notch and froze the page."""

    @pytest.fixture
    def studio(self, qt_app, tmp_path, monkeypatch):
        from crapcleaner import config as config_module
        from crapcleaner.gui.custom_theme_builder import CustomThemeBuilderWidget

        monkeypatch.setattr(config_module, "config_dir", lambda: str(tmp_path))
        widget = CustomThemeBuilderWidget()
        widget.resize(1200, 900)
        yield widget
        widget.deleteLater()

    def test_a_drag_does_not_redraw_once_per_notch(self, studio):
        redraws = []
        original = studio._update_preview
        studio._update_preview = lambda *a, **k: (redraws.append(1), original(*a, **k))[1]

        for value in range(50, 140):
            studio._on_darkness_changed(value)

        assert len(redraws) < 10, f"{len(redraws)} redraws for 90 notches"

    def test_the_value_it_ends_on_is_the_value_it_shows(self, studio, qt_app):
        for value in range(50, 140):
            studio._on_darkness_changed(value)

        studio._preview_timer.stop()
        studio._preview_cooldown()
        qt_app.processEvents()

        assert studio._current_bg_darkness == 1.39
        assert studio.darkness_val_lbl.text() == "139%"
        assert studio.preview_card._palette == generate_custom_palette(
            primary_color=studio._current_primary,
            mode=studio._current_mode,
            mood=studio._current_mood,
            surface_contrast=studio._current_contrast,
            accent_intensity=studio._current_intensity,
            bg_darkness=1.39,
        )

    def test_the_preview_is_styled_by_one_sheet(self, studio):
        """Ninety-nine setStyleSheet calls per edit is where the time went."""
        css = studio.preview_card.styleSheet()

        assert "#miniWindow" in css
        assert "#miniList QHeaderView::section" in css
        assert "#chip_accent" in css
        assert "#badge_danger" in css
        for widget in (
            studio.preview_card.mini_window,
            studio.preview_card.mini_nav,
            studio.preview_card.mini_list,
            studio.preview_card.mock_primary_btn,
        ):
            assert not widget.styleSheet(), "styled individually as well as by the sheet"

    def test_an_unchanged_palette_is_not_redrawn(self, studio):
        card = studio.preview_card
        before = card.styleSheet()
        card.setStyleSheet("/* sentinel */")

        card.update_palette(dict(card._palette), card._primary_color, card._mode, card._mood)

        assert card.styleSheet() == "/* sentinel */", "restyled for nothing"
        card.setStyleSheet(before)

    def test_the_colour_maths_is_cached(self):
        """It is called about 1,200 times per edit on two dozen distinct values."""
        from crapcleaner.gui.color_engine import contrast_ratio, relative_luminance

        for fn in (relative_luminance, contrast_ratio):
            assert hasattr(fn, "cache_info"), f"{fn.__name__} recomputes every call"

        relative_luminance("#3b82f6")
        before = relative_luminance.cache_info().hits
        for _ in range(50):
            relative_luminance("#3b82f6")

        assert relative_luminance.cache_info().hits - before == 50

    def test_the_fix_button_is_tall_enough_for_its_label(self, studio, qt_app):
        """A 24px fixed height clipped it against 13px text and 7px padding."""
        studio.show()
        qt_app.processEvents()

        assert studio.fix_btn.height() >= studio.fix_btn.sizeHint().height()
        assert studio.fix_btn.width() >= studio.fix_btn.sizeHint().width()


class TestThemingCostsWhatItShould:
    """Where the stylesheet is set decides whether a theme can be edited live."""

    def test_a_theme_is_applied_to_the_window_when_there_is_one(self, qt_app):
        """QApplication.setStyleSheet re-polishes every top-level: 1115ms against 243."""
        from PySide6.QtWidgets import QWidget

        from crapcleaner.gui.theme import apply_theme

        window = QWidget()
        try:
            qt_app.setStyleSheet("")
            apply_theme(qt_app, "dracula", window=window)

            assert window.styleSheet(), "the window was not styled"
            assert theme_module.PALETTES["dracula"]["window"] in window.styleSheet()
            assert not qt_app.styleSheet(), "styled the application as well, for nothing"
        finally:
            qt_app.setStyleSheet("")
            window.deleteLater()

    def test_without_a_window_it_falls_back_to_the_application(self, qt_app):
        """Start-up applies a theme before the window exists."""
        from crapcleaner.gui.theme import apply_theme

        try:
            apply_theme(qt_app, "dracula")

            assert theme_module.PALETTES["dracula"]["window"] in qt_app.styleSheet()
        finally:
            qt_app.setStyleSheet("")

    def test_every_dialog_is_parented(self):
        """A sheet on the window reaches a dialog only if the dialog is in its tree."""
        import pathlib
        import re

        call = re.compile(
            r"QMessageBox\.(?:information|warning|question|critical)\(\s*([^,\n]*)",
            re.M,
        )
        orphans = []
        for path in pathlib.Path("crapcleaner").rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            for match in call.finditer(source):
                parent = match.group(1).strip()
                if not parent:
                    parent = source[match.end() : match.end() + 80].strip().split(",")[0].strip()
                if parent in ("None", ""):
                    line = source[: match.start()].count("\n") + 1
                    orphans.append(f"{path}:{line}")

        assert not orphans, "unparented dialogs will not pick up the window's theme: " + ", ".join(
            orphans
        )
