"""Pytest fixtures - isolate config/history from the real user profile."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, tmp_path_factory, monkeypatch):
    """Point APPDATA/LOCALAPPDATA at a temp dir so settings/history stay isolated.

    The directories live beside `tmp_path` rather than inside it, and they are created
    rather than merely named. Both matter:

    * A tool that cannot write to the location these variables give it falls back to the
      working directory instead of failing - PowerShell puts its module cache there -
      which litters the repository with files no test asked for.
    * `tmp_path` is also the tree a storage test builds and then measures, so creating
      anything inside it changes the directory count that test is asserting on.
    """
    env_root = tmp_path_factory.mktemp("env")
    for name, path in (
        ("APPDATA", env_root / "appdata"),
        ("LOCALAPPDATA", env_root / "localappdata"),
        ("USERPROFILE", env_root / "profile"),
        ("OneDrive", env_root / "onedrive"),
        ("OneDriveConsumer", env_root / "onedrive_consumer"),
        # The same isolation for POSIX: without these the config and history resolve to
        # the real home directory, so settings written by one test are read by the next.
        ("HOME", env_root / "profile"),
        ("XDG_CONFIG_HOME", env_root / "profile" / ".config"),
        ("XDG_CACHE_HOME", env_root / "profile" / ".cache"),
        ("XDG_DATA_HOME", env_root / "profile" / ".local" / "share"),
    ):
        path.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(name, str(path))

    # PowerShell writes a module analysis cache on almost every launch, and a worker
    # thread that outlives its test launches one with whatever environment is current by
    # then. Naming the file outright is the only placement that does not depend on that
    # timing; left to itself it lands in the working directory, which is the repository.
    monkeypatch.setenv(
        "PSModuleAnalysisCachePath",
        str(env_root / "localappdata" / "ModuleAnalysisCache"),
    )
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
