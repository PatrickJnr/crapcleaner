"""Tests for the package manager backend."""

from unittest.mock import patch

from crapcleaner.system.package_managers import (
    PackageUpdate,
    _parse_choco_outdated,
    _parse_winget_upgrades,
    detect_managers,
    get_all_updates,
)

# ---------------------------------------------------------------------------
# Winget parser
# ---------------------------------------------------------------------------

_WINGET_SAMPLE = (
    "Name                   Id                           Version    Available  Source\n"
    "------------------------------------------------------------------------------------\n"
    "Visual Studio Code     Microsoft.VisualStudioCode   1.88.0     1.89.0     winget\n"
    "7-Zip 22.01 (x64)     7zip.7zip                    22.01      23.01      winget\n"
    "No applicable upgrades found.\n"
)


def test_parse_winget_typical_output():
    updates = _parse_winget_upgrades(_WINGET_SAMPLE)
    assert len(updates) == 2
    assert updates[0].id == "Microsoft.VisualStudioCode"
    assert updates[0].available_version == "1.89.0"
    assert updates[1].id == "7zip.7zip"


def test_parse_winget_empty():
    assert _parse_winget_upgrades("") == []


def test_parse_winget_no_updates():
    sample = (
        "Name Id Version Available Source\n"
        "------------------------------\n"  # long enough separator
        "No applicable upgrades found.\n"
    )
    assert _parse_winget_upgrades(sample) == []


def test_parse_winget_single_space_between_columns():
    """A value that fills its column leaves only one space before the next one."""
    sample = (
        "Name                                  Id                                       Version                  Available            Source\n"
        "-------------------------------------------------------------------------------------------------------------------------------------\n"
        "Visual Studio Professional 2022 (2)   Microsoft.VisualStudio.2022.Professional 17.14.25 (January 2026)  17.14.38             winget\n"
    )
    updates = _parse_winget_upgrades(sample)
    assert len(updates) == 1
    assert updates[0].id == "Microsoft.VisualStudio.2022.Professional"
    assert updates[0].current_version == "17.14.25 (January 2026)"
    assert updates[0].available_version == "17.14.38"
    assert updates[0].source == "winget"


# ---------------------------------------------------------------------------
# Chocolatey parser
# ---------------------------------------------------------------------------

_CHOCO_SAMPLE = "chocolatey|1.3.0|1.4.0|false\ngit|2.42.0|2.43.0|false\n"


def test_parse_choco_typical():
    updates = _parse_choco_outdated(_CHOCO_SAMPLE)
    assert len(updates) == 2
    assert updates[0].id == "chocolatey"
    assert updates[0].current_version == "1.3.0"
    assert updates[0].available_version == "1.4.0"
    assert updates[0].manager == "choco"


def test_parse_choco_empty():
    assert _parse_choco_outdated("") == []


def test_parse_choco_short_lines_skipped():
    # Line with only 2 fields (missing available version) should be skipped
    sample = "chocolatey|1.3.0\ngit|2.42.0|2.43.0|false"
    updates = _parse_choco_outdated(sample)
    assert len(updates) == 1
    assert updates[0].id == "git"


# ---------------------------------------------------------------------------
# detect_managers
# ---------------------------------------------------------------------------


def test_detect_managers_returns_list():
    result = detect_managers()
    assert isinstance(result, list)


@patch("crapcleaner.system.package_managers._cmd_exists", return_value=True)
@patch("crapcleaner.system.package_managers.is_windows", return_value=True)
@patch("crapcleaner.system.package_managers.is_linux", return_value=False)
def test_detect_windows_managers(mock_linux, mock_win, mock_exists):
    result = detect_managers()
    assert "winget" in result
    assert "choco" in result


@patch("crapcleaner.system.package_managers._cmd_exists")
@patch("crapcleaner.system.package_managers.is_windows", return_value=False)
@patch("crapcleaner.system.package_managers.is_linux", return_value=True)
def test_detect_linux_apt(mock_linux, mock_win, mock_exists):
    mock_exists.side_effect = lambda name: name == "apt"
    result = detect_managers()
    assert "apt" in result
    assert "winget" not in result


# ---------------------------------------------------------------------------
# PackageUpdate model
# ---------------------------------------------------------------------------


def test_package_update_to_dict():
    u = PackageUpdate(
        id="pkg.id",
        name="My Package",
        current_version="1.0",
        available_version="2.0",
        manager="winget",
        source="winget",
    )
    d = u.to_dict()
    assert d["id"] == "pkg.id"
    assert d["available_version"] == "2.0"
    assert d["manager"] == "winget"


# ---------------------------------------------------------------------------
# get_all_updates — no managers
# ---------------------------------------------------------------------------


@patch("crapcleaner.system.package_managers.detect_managers", return_value=[])
def test_no_managers_returns_empty(mock_detect):
    import crapcleaner.system.package_managers as pm

    pm._clear_cache()
    results = get_all_updates(force_refresh=True)
    assert results == []
