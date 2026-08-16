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
