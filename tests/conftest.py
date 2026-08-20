"""Pytest fixtures - isolate config/history from the real user profile."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Point APPDATA/LOCALAPPDATA at a temp dir so settings/history stay isolated."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "profile"))
    monkeypatch.setenv("OneDrive", str(tmp_path / "onedrive"))
    monkeypatch.setenv("OneDriveConsumer", str(tmp_path / "onedrive_consumer"))
    # The same isolation for POSIX: without these the config and history resolve to the
    # real home directory, so settings written by one test are read by the next.
    monkeypatch.setenv("HOME", str(tmp_path / "profile"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "profile" / ".config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "profile" / ".cache"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "profile" / ".local" / "share"))
    return tmp_path


@pytest.fixture
def app():
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    yield _app


@pytest.fixture
def qt_app(app):
    yield app


@pytest.fixture(autouse=True)
def cleanup_qt_widgets():
    yield
    try:
        from PySide6.QtCore import QThread
        from PySide6.QtWidgets import QApplication

        from crapcleaner.gui.workers import is_worker_running, stop_worker

        application = QApplication.instance()
        if application is not None:
            application.processEvents()
            for widget in list(application.topLevelWidgets()):
                try:
                    for thread in widget.findChildren(QThread):
                        if is_worker_running(thread):
                            stop_worker(thread, wait_ms=2000)
                    if widget.isVisible():
                        widget.close()
                    widget.deleteLater()
                except Exception:
                    pass
            application.processEvents()
    except Exception:
        pass
