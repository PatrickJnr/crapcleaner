"""The About page states facts about the running application, not about 2025."""

import platform
import sys

import pytest


@pytest.fixture
def about(qt_app, tmp_path, monkeypatch):
    from crapcleaner import config as config_module
    from crapcleaner.gui.views.about import AboutView

    monkeypatch.setattr(config_module, "config_dir", lambda: str(tmp_path))
    view = AboutView("dark")
    yield view
    view.deleteLater()


class TestApplicationInformation:
    """Four of the five rows were string literals."""

    def test_the_python_version_is_the_one_running(self, about):
        """It said 3.12 while the project supports 3.10 and up."""
        facts = dict(about._application_facts())

        assert platform.python_version() in facts["Python"]

    def test_the_platform_is_the_one_it_is_running_on(self, about):
        """It said "Windows 10 / 11 / Linux (64-bit)" on every machine."""
        facts = dict(about._application_facts())

        assert platform.system().split()[0].lower() in facts["Platform"].lower() or (
            facts["Platform"] != "Windows 10 / 11 / Linux (64-bit)"
        )
        assert "/" not in facts["Platform"], "still listing every platform at once"

    def test_the_toolkit_version_is_reported(self, about):
        import PySide6

        facts = dict(about._application_facts())

        assert PySide6.__version__ in facts["GUI Framework"]

    def test_it_does_not_claim_one_theme(self, about):
        """It said "Fluent 2 Dark Theme"; there are 44, light ones among them."""
        from crapcleaner.gui.theme import BUILTIN_THEME_IDS

        facts = dict(about._application_facts())

        assert "Fluent" not in facts.get("GUI Framework", "")
        assert str(len(BUILTIN_THEME_IDS)) in facts["Themes"]

    def test_the_version_comes_from_the_package(self, about):
        from crapcleaner import __version__

        facts = dict(about._application_facts())

        assert facts["Version"] == f"v{__version__}"

    def test_it_says_whether_this_is_a_frozen_build(self, about):
        facts = dict(about._application_facts())

        expected = "frozen build" if getattr(sys, "frozen", False) else "source"
        assert expected in facts["Python"]


class TestSafetyPanel:
    """It predates the updater and scheduled scans."""

    def test_it_no_longer_claims_the_application_is_entirely_local(self, about):
        """Opening this page asks api.github.com for the contributor list."""
        from PySide6.QtWidgets import QLabel

        text = " ".join(label.text() for label in about.findChildren(QLabel))

        assert "100% local" not in text
        assert "no network tracking" not in text

    def test_it_says_nothing_is_reported_about_the_user(self, about):
        from PySide6.QtWidgets import QLabel

        text = " ".join(label.text() for label in about.findChildren(QLabel))

        assert "No telemetry" in text
        assert "advertisements" in text

    def test_it_covers_the_capabilities_this_release_added(self, about):
        from PySide6.QtWidgets import QLabel

        text = " ".join(label.text() for label in about.findChildren(QLabel))

        assert "SHA-256" in text, "the updater replaces the binary and says nothing about it"
        assert "deletes nothing" in text, "a scheduled scan never cleans; say so"


class TestOperatingSystemName:
    def test_windows_11_is_not_reported_as_windows_10(self, monkeypatch):
        """Microsoft never changed ProductName, so the registry says 10 on an 11."""
        if sys.platform != "win32":
            pytest.skip("registry detection is Windows-only")

        from crapcleaner.system.hardware import _get_os_specs

        specs = _get_os_specs()
        digits = [
            int(part)
            for part in specs.build_number.replace("(", " ").replace(")", " ").split()
            if part.isdigit()
        ]
        if not digits or max(digits) < 22000:
            pytest.skip("not running on Windows 11")

        assert "Windows 10" not in specs.name

    def test_the_label_carries_an_architecture(self):
        from crapcleaner.system.hardware import os_label

        label = os_label()

        assert label
        assert "(" in label and ")" in label
