"""Empty, loading, and result states across the deep-scan views."""


class DummyMain:
    _settings = {}

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


def _view(cls):
    return cls(DummyMain())


def test_large_files_pre_scan_prompt(qt_app):
    from crapcleaner.gui.views import LargeFilesView

    view = _view(LargeFilesView)
    assert "Find Large Files" in view._empty_message


def test_large_files_empty_result_is_distinct_from_prompt(qt_app):
    from crapcleaner.gui.views import LargeFilesView

    view = _view(LargeFilesView)
    view.show_files([])
    assert "Scan complete" in view._empty_message
    assert view.table.rowCount() == 0
    assert view.scan_button.isEnabled()
    assert not view.cancel_button.isVisible()


def test_duplicates_empty_result_is_distinct_from_prompt(qt_app):
    from crapcleaner.gui.views import DuplicatesView

    view = _view(DuplicatesView)
    prompt = view._empty_message
    view.show_groups([])
    assert view._empty_message != prompt
    assert "No duplicate files" in view._empty_message


def test_ai_data_empty_result_is_distinct_from_prompt(qt_app):
    from crapcleaner.gui.views import AiDataView

    view = _view(AiDataView)
    prompt = view._empty_message
    view.show_items([])
    assert view._empty_message != prompt
    assert "No local AI models" in view._empty_message


def test_theme_change_keeps_the_current_empty_message(qt_app):
    from crapcleaner.gui.views import DuplicatesView

    view = _view(DuplicatesView)
    view.show_groups([])
    after_scan = view._empty_message
    view.apply_theme("oled")
    assert view._empty_message == after_scan


def test_cleaning_state_reports_progress_and_locks_the_button(qt_app):
    from crapcleaner.gui.views import CleanupView

    view = _view(CleanupView)
    view.set_cleaning(True, 3)
    assert view.clean_button.isEnabled() is False
    assert view.progress_bar.maximum() == 3

    view.set_clean_progress("Temp files", 2)
    assert view.progress_bar.value() == 2
    assert "Temp files" in view.status_label.text()

    view.set_cleaning(False)
    view.clear_status()
    assert view.clean_button.isEnabled() is True
    assert view.status_label.text() == ""


def _cleanup_dialog(dry_run: bool = True, use_recycle_bin: bool = True):
    from crapcleaner.gui.dialogs import ConfirmCleanupDialog
    from crapcleaner.models.category import CleanupCategory, SafetyLevel

    category = CleanupCategory(
        id="demo_cache",
        name="Demo cache",
        group="Demo",
        description="",
        safety_level=SafetyLevel.LOW_RISK,
        what_it_contains="",
        why_safe_to_delete="",
    )
    return ConfirmCleanupDialog(
        [category], dry_run_default=dry_run, use_recycle_bin_default=use_recycle_bin
    )


def test_cleanup_mode_is_one_exclusive_choice(qt_app):
    dialog = _cleanup_dialog()

    # Two checkboxes let you ask for a dry run that also recycles, which means nothing.
    assert dialog.dry_run_radio.isChecked()
    assert not dialog.recycle_radio.isChecked()
    assert not dialog.permanent_radio.isChecked()

    dialog.recycle_radio.setChecked(True)
    assert not dialog.dry_run_radio.isChecked()
    assert not dialog.permanent_radio.isChecked()

    dialog.permanent_radio.setChecked(True)
    assert not dialog.recycle_radio.isChecked()


def test_every_cleanup_mode_stays_reachable(qt_app):
    dialog = _cleanup_dialog()

    dialog.recycle_radio.setChecked(True)
    assert not dialog.is_dry_run()
    assert dialog.use_recycle_bin()

    dialog.permanent_radio.setChecked(True)
    assert not dialog.is_dry_run()
    assert not dialog.use_recycle_bin()

    dialog.dry_run_radio.setChecked(True)
    assert dialog.is_dry_run()


def test_a_dry_run_reports_the_saved_deletion_preference(qt_app):
    # It deletes nothing, so it must not claim the permanent deletion no radio stands for.
    assert _cleanup_dialog(use_recycle_bin=True).use_recycle_bin()
    assert not _cleanup_dialog(use_recycle_bin=False).use_recycle_bin()


def test_the_dialog_opens_on_the_saved_deletion_mode(qt_app):
    assert _cleanup_dialog(dry_run=False, use_recycle_bin=True).recycle_radio.isChecked()
    assert _cleanup_dialog(dry_run=False, use_recycle_bin=False).permanent_radio.isChecked()


def test_a_checked_box_is_drawn_with_a_tick(qt_app):
    from crapcleaner.gui.theme.palettes import palette_for
    from crapcleaner.gui.theme.stylesheet import _build_stylesheet

    sheet = _build_stylesheet(palette_for("dark"))
    checked = sheet.split("QCheckBox::indicator:checked")[1].split("}")[0]

    # A filled square alone reads as a colour swatch rather than as a chosen option.
    assert "image: url(" in checked
