"""Tests for the platform capability registry and the platform-aware navigation.

A second operating system is not available here, so the Linux paths are validated by
pinning the registry to Linux and asserting on what the application would build.
"""

from contextlib import contextmanager
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

from crapcleaner.gui.sidebar import NAV_SECTIONS, Sidebar, nav_label
from crapcleaner.system.capabilities import (
    APP_UPDATES,
    SERVICES,
    STARTUP,
    SYSTEM_UPDATES,
    capability_summary,
    get_capability,
    is_supported,
    supported_capabilities,
)

_app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])


@contextmanager
def force_platform(name: str, tooling: bool = True):
    with patch("crapcleaner.system.capabilities.is_windows", return_value=name == "windows"):
        with patch("crapcleaner.system.capabilities.is_linux", return_value=name == "linux"):
            with patch("crapcleaner.system.capabilities._has", return_value=tooling):
                yield


ALL_KEYS = (STARTUP, SERVICES, SYSTEM_UPDATES, APP_UPDATES)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", ALL_KEYS)
def test_every_capability_is_described_on_both_platforms(key):
    for platform in ("windows", "linux"):
        with force_platform(platform):
            capability = get_capability(key)
        assert capability.supported is True
        assert capability.platform == platform
        assert capability.nav_label
        assert capability.title
        assert capability.subtitle
        assert capability.terms.get("os_name")


@pytest.mark.parametrize("key", ALL_KEYS)
def test_unknown_platform_reports_unsupported_with_a_reason(key):
    with force_platform("plan9"):
        capability = get_capability(key)
        assert is_supported(key) is False
    assert capability.supported is False
    assert capability.unsupported_reason


def test_platform_specific_wording_differs_where_it_should():
    with force_platform("windows"):
        assert get_capability(SERVICES).title == "Windows Services"
        assert get_capability(SYSTEM_UPDATES).title == "Windows Updates"
        assert get_capability(SERVICES).terms["unit_noun"] == "service"
    with force_platform("linux"):
        assert get_capability(SERVICES).title == "systemd Services"
        assert get_capability(SYSTEM_UPDATES).title == "System Updates"
        assert get_capability(SERVICES).terms["unit_noun"] == "unit"


def test_nav_label_is_shared_where_the_concept_is_shared():
    """The rail reads the same on both platforms; only the page bodies differ."""
    with force_platform("windows"):
        windows_labels = {k: get_capability(k).nav_label for k in ALL_KEYS}
    with force_platform("linux"):
        linux_labels = {k: get_capability(k).nav_label for k in ALL_KEYS}
    assert windows_labels == linux_labels


def test_missing_tooling_makes_a_capability_unsupported():
    with force_platform("linux", tooling=False):
        services = get_capability(SERVICES)
        updates = get_capability(SYSTEM_UPDATES)
        # Startup needs no external tool, so it stays available.
        assert get_capability(STARTUP).supported is True

    assert services.supported is False
    assert "systemd" in services.unsupported_reason
    assert updates.supported is False
    assert "package manager" in updates.unsupported_reason


def test_supported_capabilities_and_summary():
    with force_platform("linux", tooling=False):
        keys = {c.key for c in supported_capabilities()}
        summary = capability_summary()

    assert SERVICES not in keys
    assert STARTUP in keys
    assert summary[SERVICES]["supported"] is False
    assert summary[SERVICES]["reason"]
    assert set(summary) == set(ALL_KEYS)


# ---------------------------------------------------------------------------
# Navigation rail
# ---------------------------------------------------------------------------


def _page_keys():
    from crapcleaner.gui.app import MainWindow

    return MainWindow._build_page_keys()


def test_page_keys_include_every_capability_when_supported():
    with force_platform("windows"):
        keys = _page_keys()
    for key in ALL_KEYS:
        assert key in keys
    assert keys[0] == "dashboard"
    assert keys[-1] == "about"


def test_page_keys_drop_capabilities_the_platform_lacks():
    with force_platform("linux", tooling=False):
        keys = _page_keys()

    assert SERVICES not in keys
    assert SYSTEM_UPDATES not in keys
    # Everything that does not depend on missing tooling survives.
    assert STARTUP in keys
    assert APP_UPDATES in keys
    assert "dashboard" in keys and "settings" in keys


def test_sidebar_only_builds_buttons_for_supported_pages():
    with force_platform("linux", tooling=False):
        keys = _page_keys()
        sidebar = Sidebar("1.0.9", page_keys=keys)

    assert SERVICES not in sidebar._buttons
    assert SYSTEM_UPDATES not in sidebar._buttons
    assert STARTUP in sidebar._buttons
    sidebar.deleteLater()


def test_sidebar_sections_collapse_when_fully_hidden():
    """A section whose every item is unavailable must not render a bare heading."""
    only_overview = ["dashboard", "cleanup", "storage"]
    sidebar = Sidebar("1.0.9", page_keys=only_overview)
    assert set(sidebar._buttons) == set(only_overview)
    sidebar.deleteLater()


def test_nav_label_falls_back_for_non_capability_pages():
    assert nav_label("dashboard", "Dashboard") == "Dashboard"
    assert nav_label("settings", "Settings") == "Settings"


def test_every_nav_item_has_a_page_key_on_windows():
    """A rail entry with no page behind it would navigate nowhere."""
    with force_platform("windows"):
        keys = set(_page_keys())
    nav_keys = {key for _section, items in NAV_SECTIONS for key, _lbl, _icon in items}
    assert nav_keys == keys
