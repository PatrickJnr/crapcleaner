"""Static cross-platform validation of the platform-aware views.

Only one operating system is available at test time, so the other is validated by
pinning the capability registry and asserting on what the views actually build: their
headings, their vocabulary, and the platform commands they would issue.
"""

from contextlib import contextmanager
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

from crapcleaner.gui.views import ServicesView, StartupView, SystemUpdatesView, WindowsUpdateView

_app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])


@contextmanager
def force_platform(name: str, tooling: bool = True):
    with patch("crapcleaner.system.capabilities.is_windows", return_value=name == "windows"):
        with patch("crapcleaner.system.capabilities.is_linux", return_value=name == "linux"):
            with patch("crapcleaner.system.capabilities._has", return_value=tooling):
                yield


def _text_of(view) -> str:
    """Every string the view renders, flattened for substring assertions."""
    from PySide6.QtWidgets import QComboBox, QLabel, QPushButton

    parts: list[str] = []
    for child in view.findChildren(QLabel):
        parts.append(child.text())
    for child in view.findChildren(QPushButton):
        parts.append(child.text())
    for child in view.findChildren(QComboBox):
        parts.extend(child.itemText(i) for i in range(child.count()))
    for table in ("table", "avail_table", "hist_table"):
        widget = getattr(view, table, None)
        if widget is None:
            continue
        parts.extend(
            widget.horizontalHeaderItem(col).text()
            for col in range(widget.columnCount())
            if widget.horizontalHeaderItem(col) is not None
        )
    return "\n".join(p for p in parts if p)


def test_startup_view_speaks_windows_on_windows():
    with force_platform("windows"):
        view = StartupView(None)
    text = _text_of(view)
    assert "Startup Applications" in text
    assert "when Windows starts" in text
    view.deleteLater()


def test_startup_view_speaks_xdg_on_linux():
    with force_platform("linux"):
        view = StartupView(None)
    text = _text_of(view)
    assert "Startup Applications" in text
    assert "XDG autostart" in text
    assert "Windows" not in text
    view.deleteLater()


def test_services_view_speaks_windows_on_windows():
    with force_platform("windows"):
        view = ServicesView(None)
    text = _text_of(view)
    assert "Windows Services" in text
    assert "services.msc" in text
    assert "Automatic (Delayed Start)" in text  # Windows-only startup type
    view.deleteLater()


def test_services_view_speaks_systemd_on_linux():
    with force_platform("linux"):
        view = ServicesView(None)
    text = _text_of(view)
    assert "systemd Services" in text
    assert "systemd Manager" in text
    assert "services.msc" not in text
    # systemd has no delayed-start mode, so the filter must not offer one.
    assert "Automatic (Delayed Start)" not in text
    assert "Automatic" in text and "Disabled" in text
    view.deleteLater()


def test_services_view_startup_menu_matches_the_platform():
    with force_platform("windows"):
        windows_view = ServicesView(None)
    with force_platform("linux"):
        linux_view = ServicesView(None)

    assert "Automatic (Delayed Start)" in windows_view._startup_types
    assert linux_view._startup_types == ["Automatic", "Manual", "Disabled"]
    windows_view.deleteLater()
    linux_view.deleteLater()


def test_updates_view_speaks_windows_update_on_windows():
    with force_platform("windows"):
        view = SystemUpdatesView(None)
    text = _text_of(view)
    assert "Windows Updates" in text
    assert "KB Article" in text
    assert "Hotfix" in text or "HotFix" in text
    view.deleteLater()


def test_updates_view_speaks_package_manager_on_linux():
    with force_platform("linux"):
        view = SystemUpdatesView(None)
    text = _text_of(view)
    assert "System Updates" in text
    assert "package manager" in text
    assert "KB Article" not in text
    assert "HotFix ID" not in text
    assert "Windows" not in text
    view.deleteLater()


def test_updates_view_alias_is_the_same_class():
    assert WindowsUpdateView is SystemUpdatesView


@contextmanager
def force_memory_platform(name: str):
    """Memory actions gate on the platform helpers imported into their own module."""
    import crapcleaner.system.memory_actions as memory_actions

    with patch.object(memory_actions, "is_windows", return_value=name == "windows"):
        with patch.object(memory_actions, "is_linux", return_value=name == "linux"):
            yield


def test_memory_view_hides_linux_actions_on_windows():
    from crapcleaner.gui.views import MemoryView

    with force_memory_platform("windows"):
        view = MemoryView(None)
    text = _text_of(view)

    assert set(view._action_cards) == {
        "flush_all",
        "process_working_sets",
        "working_set",
        "standby_list",
        "vram_report",
    }
    for token in ("drop_caches", "malloc_trim", "/proc/sys", "Linux"):
        assert token not in text
    view.deleteLater()


def test_memory_view_hides_windows_actions_on_linux():
    from crapcleaner.gui.views import MemoryView

    with force_memory_platform("linux"):
        view = MemoryView(None)
    text = _text_of(view)

    assert set(view._action_cards) == {
        "flush_all",
        "process_working_sets",
        "working_set",
        "fs_cache",
        "vram_report",
    }
    assert "drop_caches" in text and "malloc_trim" in text
    for token in ("EmptyWorkingSet", "SetProcessWorkingSetSize", "standby"):
        assert token not in text
    view.deleteLater()


@pytest.mark.parametrize(
    "module_name",
    [
        "crapcleaner.system.backends.services_linux",
        "crapcleaner.system.backends.updates_linux",
        "crapcleaner.system.backends.startup_linux",
    ],
)
def test_linux_backends_never_invoke_powershell(module_name):
    import importlib
    import inspect

    source = inspect.getsource(importlib.import_module(module_name))
    assert "powershell" not in source.lower()
    assert "winreg" not in source
    assert "sc.exe" not in source


@pytest.mark.parametrize(
    "module_name",
    [
        "crapcleaner.system.backends.services_windows",
        "crapcleaner.system.backends.updates_windows",
        "crapcleaner.system.backends.startup_windows",
    ],
)
def test_windows_backends_never_invoke_linux_tooling(module_name):
    import importlib
    import inspect

    source = inspect.getsource(importlib.import_module(module_name))
    for tool in ("systemctl", "pkexec", "apt-get", "/etc/xdg"):
        assert tool not in source


def test_dispatchers_contain_no_platform_branching():
    """Platform choices belong in the registry, not scattered through dispatchers."""
    import inspect

    from crapcleaner.system import services, startup, system_updates

    for module in (services, startup, system_updates):
        source = inspect.getsource(module)
        assert "is_windows()" not in source
        assert "is_linux()" not in source
