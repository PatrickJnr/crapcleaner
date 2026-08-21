"""The AppImage the workflow builds must be the one the updater goes looking for.

An AppImage replaces itself with the asset named by `APPIMAGE_ASSET`. If the workflow
publishes it under a different name, or stops publishing it, the download fails with
"the release does not publish a checksum for ..." and self-update is broken for every
AppImage user, while every test that only looks at Python still passes.
"""

import configparser
import pathlib

from crapcleaner.utils.self_update import APPIMAGE_ASSET

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_RELEASE = _ROOT / ".github" / "workflows" / "release.yml"
_DESKTOP = _ROOT / "packaging" / "crapcleaner.desktop"


def test_the_release_publishes_the_asset_the_updater_asks_for():
    workflow = _RELEASE.read_text(encoding="utf-8")

    assert APPIMAGE_ASSET in workflow, (
        f"the updater downloads {APPIMAGE_ASSET}; the release workflow never names it"
    )


def test_the_appimage_is_listed_among_the_release_files():
    """Building it and forgetting to attach it is the easy mistake."""
    workflow = _RELEASE.read_text(encoding="utf-8")
    files_block = workflow.split("files: |", 1)[1].split("draft:", 1)[0]

    assert APPIMAGE_ASSET in files_block


def test_the_appimage_is_covered_by_the_checksums():
    """The updater refuses any download it cannot verify, so an unlisted asset is dead."""
    workflow = _RELEASE.read_text(encoding="utf-8")
    checksum_line = next(
        line for line in workflow.splitlines() if "sha256sum" in line and "checksums.txt" in line
    )

    assert (
        APPIMAGE_ASSET in checksum_line or APPIMAGE_ASSET in workflow.split(checksum_line)[1][:200]
    )


def test_the_desktop_entry_is_complete_enough_to_install():
    """appimagetool refuses a desktop entry missing any of these."""
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(_DESKTOP, encoding="utf-8")
    entry = parser["Desktop Entry"]

    assert entry["Type"] == "Application"
    assert entry["Name"]
    assert entry["Exec"]
    assert entry["Icon"] == "crapcleaner", "must match the icon file's basename"
    for key in ("Categories", "Keywords"):
        assert entry[key].endswith(";"), f"{key} is a list and must end with a semicolon"


def test_the_desktop_entry_does_not_claim_to_open_files():
    """CrapCleaner takes flags, not paths; %F would offer it as a file handler."""
    entry = _DESKTOP.read_text(encoding="utf-8")

    assert "%F" not in entry and "%U" not in entry
