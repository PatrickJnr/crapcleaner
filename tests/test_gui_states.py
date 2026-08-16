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
