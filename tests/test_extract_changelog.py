"""Unit tests for scripts/extract_changelog.py."""

import tempfile
from pathlib import Path

from scripts.extract_changelog import extract_changelog, extract_release_title

SAMPLE_CHANGELOG = """# Changelog

All notable changes to **CrapCleaner** will be documented in this file.

---

## [1.0.7] - 2026-08-20

Feature improvements release.

### Added
- Feature A in 1.0.7
- Feature B in 1.0.7

---

## [1.0.6] - 2026-08-16

Theme Gallery release.

### Added
- Visual Theme Gallery

### Changed
- Branding cleanup

---

## [1.0.5] - 2026-08-16

Repository reorganization.
"""


def test_extract_exact_version():
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
        f.write(SAMPLE_CHANGELOG)
        tmp_path = Path(f.name)

    try:
        notes_107 = extract_changelog("1.0.7", tmp_path)
        assert "Feature improvements release." in notes_107
        assert "Feature A in 1.0.7" in notes_107
        assert "1.0.6" not in notes_107

        # With leading 'v'
        notes_v106 = extract_changelog("v1.0.6", tmp_path)
        assert "Theme Gallery release." in notes_v106
        assert "Visual Theme Gallery" in notes_v106
        assert "1.0.7" not in notes_v106

        # With refs/tags/v prefix
        notes_ref = extract_changelog("refs/tags/v1.0.5", tmp_path)
        assert "Repository reorganization." in notes_ref
    finally:
        tmp_path.unlink(missing_ok=True)


def test_extract_topmost_when_no_version_specified():
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
        f.write(SAMPLE_CHANGELOG)
        tmp_path = Path(f.name)

    try:
        notes_top = extract_changelog(None, tmp_path)
        assert "Feature improvements release." in notes_top
        assert "Feature A in 1.0.7" in notes_top
        assert "1.0.6" not in notes_top
    finally:
        tmp_path.unlink(missing_ok=True)


def test_extract_release_title():
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
        f.write(SAMPLE_CHANGELOG)
        tmp_path = Path(f.name)

    try:
        title_107 = extract_release_title("1.0.7", tmp_path)
        assert title_107 == "v1.0.7: Feature improvements release"

        title_v106 = extract_release_title("v1.0.6", tmp_path)
        assert title_v106 == "v1.0.6: Theme Gallery release"

        title_top = extract_release_title(None, tmp_path)
        assert title_top == "v1.0.7: Feature improvements release"
    finally:
        tmp_path.unlink(missing_ok=True)


def test_extract_nonexistent_file():
    notes = extract_changelog("1.0.6", "non_existent_file.md")
    assert notes == ""
    title = extract_release_title("1.0.6", "non_existent_file.md")
    assert title == "v1.0.6"
