"""Pytest fixtures - isolate config/history from the real user profile."""

import os
import sys

import pytest

# Ensure tests run from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Point APPDATA/LOCALAPPDATA at a temp dir so settings/history stay isolated."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "profile"))
    monkeypatch.setenv("OneDrive", str(tmp_path / "onedrive"))
    monkeypatch.setenv("OneDriveConsumer", str(tmp_path / "onedrive_consumer"))
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

        application = QApplication.instance()
        if application is not None:
            application.processEvents()
            for widget in list(application.topLevelWidgets()):
                try:
                    for thread in widget.findChildren(QThread):
                        if thread.isRunning():
                            thread.quit()
                            thread.wait(2000)
                    if widget.isVisible():
                        widget.close()
                    widget.deleteLater()
                except Exception:
                    pass
            application.processEvents()
    except Exception:
        pass
