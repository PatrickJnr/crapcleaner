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


WRAPPED_CHANGELOG = """# Changelog

## [1.1.0] - 2026-08-20

The codebase audit, implemented, and the features it recommended. Deletion
outside the cleanup engine now goes through the same protected-path layer; the
shipped executable honours command-line arguments.

### Added
- A thing
"""

LONG_SENTENCE_CHANGELOG = """# Changelog

## [2.0.0] - 2026-08-20

A single enormous opening sentence that simply keeps going and going and going well past anything a release list could sensibly display on one line at all.

### Added
- A thing
"""


def _titled(text, version):
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f:
        f.write(text)
        tmp_path = Path(f.name)
    try:
        return extract_release_title(version, tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def test_a_wrapped_summary_is_not_cut_at_the_wrap():
    """v1.1.0 published as "...it recommended. Deletion" - the next sentence's first word."""
    title = _titled(WRAPPED_CHANGELOG, "1.1.0")

    assert title == "v1.1.0: The codebase audit, implemented, and the features it recommended"
    assert not title.endswith("Deletion")


def test_only_the_first_sentence_is_used():
    title = _titled(WRAPPED_CHANGELOG, "1.1.0")

    assert "protected-path" not in title, "the whole paragraph ended up in the title"


def test_a_runaway_sentence_is_cut_on_a_word_boundary():
    title = _titled(LONG_SENTENCE_CHANGELOG, "2.0.0")

    assert len(title) < 120, f"{len(title)} characters is not a title"
    assert title.endswith("\u2026")
    # Cut between words, not through one.
    assert not title.rstrip("\u2026").endswith(" ")
    assert "goin\u2026" not in title


def test_the_real_changelog_produces_a_readable_title():
    """Every published release is 38-63 characters; a new one should match."""
    title = extract_release_title(None, "CHANGELOG.md")

    assert title.startswith("v")
    assert len(title) <= 80, f"{len(title)} characters: {title}"
    assert "  " not in title
    assert not title.endswith("…"), "the opening sentence is doing too much"
