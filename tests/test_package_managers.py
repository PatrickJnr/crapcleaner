"""Tests for the package manager backend."""

from unittest.mock import patch

from crapcleaner.system.package_managers import (
    PackageUpdate,
    _parse_choco_outdated,
    _parse_winget_upgrades,
    detect_managers,
    get_all_updates,
)

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
    sample = "chocolatey|1.3.0\ngit|2.42.0|2.43.0|false"
    updates = _parse_choco_outdated(sample)
    assert len(updates) == 1
    assert updates[0].id == "git"


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


@patch("crapcleaner.system.package_managers.detect_managers", return_value=[])
def test_no_managers_returns_empty(mock_detect):
    import crapcleaner.system.package_managers as pm

    pm._clear_cache()
    results = get_all_updates(force_refresh=True)
    assert results == []


def _elevation(monkeypatch, *, helper="pkexec"):
    """Record every command `elevated` runs, with `helper` as the only elevator."""
    from crapcleaner.system.backends import updates_linux

    calls: list[list[str]] = []

    def record(args, **_kwargs):
        calls.append(list(args))
        return {"returncode": 0, "stdout": "done", "stderr": ""}

    monkeypatch.setattr(updates_linux, "run_command", record)
    monkeypatch.setattr(
        updates_linux.shutil, "which", lambda t: f"/usr/bin/{t}" if t == helper else None
    )
    monkeypatch.setattr(updates_linux.os, "geteuid", lambda: 1000, raising=False)
    return calls


def test_every_linux_install_runs_elevated(monkeypatch):
    """XP-03: only apt was wrapped, so Arch, Fedora and openSUSE installs always failed."""
    import crapcleaner.system.package_managers as pm

    for manager, expected in (
        ("pacman", ["pacman", "-S", "--noconfirm", "vim"]),
        ("dnf", ["dnf", "upgrade", "-y", "vim"]),
        ("yum", ["yum", "upgrade", "-y", "vim"]),
        ("snap", ["snap", "refresh", "vim"]),
        ("apt", ["apt", "install", "--only-upgrade", "-y", "vim"]),
    ):
        calls = _elevation(monkeypatch)
        ok, _msg = pm.install_update(manager, "vim")
        assert ok is True
        assert calls == [["pkexec"] + expected], manager


def test_install_all_runs_elevated(monkeypatch):
    import crapcleaner.system.package_managers as pm

    calls = _elevation(monkeypatch)
    ok, _msg = pm.install_all_updates("pacman")
    assert ok is True
    assert calls == [["pkexec", "pacman", "-Syu", "--noconfirm"]]


def test_install_without_an_elevation_helper_explains_itself(monkeypatch):
    import crapcleaner.system.package_managers as pm

    _elevation(monkeypatch, helper="none")
    ok, message = pm.install_update("pacman", "vim")
    assert ok is False
    assert "pkexec" in message and "sudo" in message


_APT_DRY_RUN = (
    "Reading package lists...\n"
    "Inst linux-image-generic [6.8.0-31] (6.8.0-40 Ubuntu:24.04/noble-security [amd64])\n"
    "Inst curl [8.5.0-2] (8.5.0-2ubuntu10.1 Ubuntu:24.04/noble-updates [amd64])\n"
    "Conf curl (8.5.0-2ubuntu10.1 Ubuntu:24.04/noble-updates [amd64])\n"
)


def test_apt_is_queried_once_for_both_update_views(monkeypatch):
    """XP-04: the App Updates and System Updates views must not disagree."""
    import crapcleaner.system.package_managers as pm
    from crapcleaner.system.backends import updates_linux

    commands: list[list[str]] = []

    def fake_run(args, **_kwargs):
        commands.append(list(args))
        return 0, _APT_DRY_RUN, ""

    monkeypatch.setattr(pm, "_run", fake_run)

    app_view = pm._get_apt_updates("apt")
    system_view = updates_linux._check_apt()

    assert [(u.id, u.current_version, u.available_version) for u in app_view.updates] == [
        (name, current, available) for name, current, available, _source in system_view
    ]
    assert {u.id for u in app_view.updates} == {"linux-image-generic", "curl"}
    assert len(commands) == 2 and commands[0] == commands[1]
    for command in commands:
        assert "sudo" not in command and "update" not in command


def test_offline_mode_skips_every_package_check(monkeypatch):
    """FEAT-15: no package manager may be asked to contact a remote source."""
    import crapcleaner.system.package_managers as pm

    def explode(*_args, **_kwargs):
        raise AssertionError("offline mode must not run a package manager")

    monkeypatch.setattr(pm, "offline_mode", lambda: True)
    monkeypatch.setattr(pm, "_run", explode)
    monkeypatch.setattr(pm, "detect_managers", lambda: ["winget", "apt", "snap"])

    results = pm.get_all_updates(force_refresh=True)
    assert [r.manager for r in results] == ["winget", "apt", "snap"]
    for result in results:
        assert result.updates == []
        assert "offline mode" in result.error
