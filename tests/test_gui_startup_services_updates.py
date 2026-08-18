"""Integration and GUI tests for StartupView, WindowsUpdateView, and ServicesView."""

from crapcleaner.gui.app import MainWindow
from crapcleaner.gui.views import (
    AddStartupDialog,
)
from crapcleaner.system.services import ServiceItem
from crapcleaner.system.startup import StartupItem
from crapcleaner.system.windows_updates import (
    WindowsUpdateItem,
    WindowsUpdateReport,
)


def _sample_startup_items():
    return [
        StartupItem(
            id="reg:HKCU_RUN:Discord",
            name="Discord",
            command="C:\\Users\\User\\AppData\\Local\\Discord\\app.exe",
            location="Registry (Current User Run)",
            location_key="HKCU_RUN",
            scope="USER",
            enabled=True,
            impact="High",
            publisher="Discord Inc.",
            file_path="C:\\Users\\User\\AppData\\Local\\Discord\\app.exe",
            file_exists=True,
        ),
        StartupItem(
            id="reg:HKLM_RUN:OneDrive",
            name="OneDrive",
            command="C:\\Program Files\\OneDrive\\onedrive.exe /background",
            location="Registry (All Users Run)",
            location_key="HKLM_RUN",
            scope="SYSTEM",
            enabled=False,
            impact="Medium",
            publisher="Microsoft Corporation",
            file_path="C:\\Program Files\\OneDrive\\onedrive.exe",
            file_exists=True,
        ),
    ]


def _sample_update_report():
    return WindowsUpdateReport(
        available_updates=[
            WindowsUpdateItem(
                id="KB5041585",
                title="Cumulative Update for Windows 11 (KB5041585)",
                kb_numbers=["KB5041585"],
                description="Security update for Windows 11.",
                size_bytes=500 * 1024 * 1024,
                categories=["Security Updates"],
                severity="Critical",
                is_downloaded=True,
                is_mandatory=True,
                support_url="https://support.microsoft.com/kb/5041585",
                status="Downloaded",
            )
        ],
        installed_history=[
            WindowsUpdateItem(
                id="KB5001122",
                title="KB5001122 (Security Update)",
                kb_numbers=["KB5001122"],
                description="Installed by: NT AUTHORITY\\SYSTEM",
                size_bytes=0,
                categories=["Security Update"],
                severity="Installed",
                is_downloaded=True,
                is_mandatory=False,
                support_url="",
                installed_on="2026-08-01",
                status="Installed",
            )
        ],
        service_status="Running",
        error=None,
    )


def _sample_services():
    return [
        ServiceItem(
            name="wuauserv",
            display_name="Windows Update",
            status="Running",
            startup_type="Manual",
            description="Detects and downloads updates.",
            account="LocalSystem",
            pid=1200,
            is_system=True,
            can_stop=True,
        ),
        ServiceItem(
            name="CustomToolSvc",
            display_name="Third Party Tool Service",
            status="Stopped",
            startup_type="Disabled",
            description="Third-party background helper.",
            account="LocalSystem",
            pid=None,
            is_system=False,
            can_stop=True,
        ),
    ]


def test_startup_view_population_and_filtering(qt_app):
    win = MainWindow()
    view = win.startup_view

    items = _sample_startup_items()
    view._on_startup_loaded(items)

    assert view.table.rowCount() == 2
    assert view.hero_badge.text() == "2 APPS"
    assert view.enabled_badge.text() == "1 ENABLED"
    assert view.disabled_badge.text() == "1 DISABLED"
    assert view.total_card_val.text() == "2"
    assert view.enabled_card_val.text() == "1"
    assert view.disabled_card_val.text() == "1"

    # Search filter
    view.search_input.setText("Discord")
    assert view.table.rowCount() == 1
    assert view.table.item(0, 1).text() == "Discord"

    # Reset search and test scope filter
    view.search_input.setText("")
    view.scope_combo.setCurrentText("All Users (HKLM)")
    assert view.table.rowCount() == 1
    assert view.table.item(0, 1).text() == "OneDrive"

    # State filter
    view.scope_combo.setCurrentText("All Scopes")
    view.state_combo.setCurrentText("Enabled Only")
    assert view.table.rowCount() == 1
    assert view.table.item(0, 1).text() == "Discord"

    # Theme application
    view.apply_theme("dracula")


def test_windows_update_view_population_and_filtering(qt_app):
    win = MainWindow()
    view = win.updates_view

    rep = _sample_update_report()
    view._on_updates_loaded(rep)

    assert view.avail_table.rowCount() == 1
    assert view.avail_table.item(0, 0).text() == "Cumulative Update for Windows 11 (KB5041585)"
    assert view.hist_table.rowCount() == 1
    assert view.hist_table.item(0, 0).text() == "KB5001122"

    assert view.avail_card_val.text() == "1"
    assert view.crit_card_val.text() == "1"
    assert view.hist_card_val.text() == "1"

    # History search
    view.hist_search.setText("KB5001122")
    assert view.hist_table.rowCount() == 1
    view.hist_search.setText("NonExistentKB")
    assert view.hist_table.rowCount() == 0

    # Theme application
    view.apply_theme("catppuccin_mocha")


def test_services_view_population_and_filtering(qt_app):
    win = MainWindow()
    view = win.services_view

    svcs = _sample_services()
    view._on_services_loaded(svcs)

    assert view.table.rowCount() == 2
    # The noun follows the platform: "services" on Windows, "units" under systemd.
    # Asserting one platform's wording is what this used to get wrong.
    assert view.hero_badge.text() == f"2 {view._unit_plural.upper()}"
    assert view.running_badge.text() == "1 RUNNING"
    assert view.stopped_badge.text() == "1 STOPPED"

    # Search filter
    view.search_input.setText("wuauserv")
    assert view.table.rowCount() == 1
    assert view.table.item(0, 1).text() == "wuauserv"

    # Status filter
    view.search_input.setText("")
    view.status_combo.setCurrentText("Running Only")
    assert view.table.rowCount() == 1
    assert view.table.item(0, 1).text() == "wuauserv"

    # Third-party filter
    view.status_combo.setCurrentText("All Status")
    view.type_combo.setCurrentText("Third-Party Only")
    assert view.table.rowCount() == 1
    assert view.table.item(0, 1).text() == "CustomToolSvc"

    # Theme application
    view.apply_theme("nord")


def test_main_window_navigation_to_new_pages(qt_app):
    win = MainWindow()

    win.navigate("startup")
    assert win.stack.currentWidget() == win.startup_view

    win.navigate("services")
    assert win.stack.currentWidget() == win.services_view

    win.navigate("updates")
    assert win.stack.currentWidget() == win.updates_view


def test_add_startup_dialog(qt_app):
    dlg = AddStartupDialog()
    dlg.name_input.setText("Test Tool")
    dlg.path_input.setText("C:\\Tool\\tool.exe")
    dlg.scope_combo.setCurrentIndex(0)

    name, path, scope = dlg.get_data()
    assert name == "Test Tool"
    assert path == "C:\\Tool\\tool.exe"
    assert scope == "USER"
