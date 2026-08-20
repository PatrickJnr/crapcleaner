"""FEAT-14: the catalogue is generated from category metadata, so it cannot go stale."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel  # noqa: E402
from crapcleaner.registry import get_all_categories  # noqa: E402
from scripts.generate_category_catalogue import main, render  # noqa: E402


def _category(**overrides) -> CleanupCategory:
    fields = {
        "id": "example_cache",
        "name": "Example cache",
        "description": "Fixture",
        "safety_level": SafetyLevel.SAFE,
        "group": "Browsers",
        "targets": [CacheTarget(path="C:/example")],
        "what_it_contains": "Cached images and scripts.",
        "why_it_grows": "Repeat visits cache more assets.",
        "why_safe_to_delete": "Preserves bookmarks and passwords.",
        "regeneration_behavior": "Re-downloaded on the next visit.",
    }
    fields.update(overrides)
    return CleanupCategory(**fields)


def test_every_metadata_field_reaches_the_page():
    page = render([_category()])
    assert "### Example cache" in page
    assert "`example_cache`" in page
    for text in (
        "Cached images and scripts.",
        "Repeat visits cache more assets.",
        "Preserves bookmarks and passwords.",
        "Re-downloaded on the next visit.",
    ):
        assert text in page, f"missing: {text}"


def test_categories_are_grouped_and_admin_is_flagged():
    page = render(
        [
            _category(id="a_cache", name="A cache", group="Browsers"),
            _category(id="b_dump", name="B dump", group="System", requires_admin=True),
        ]
    )
    assert page.index("## Browsers") < page.index("## System")
    assert "Requires administrator rights." in page


def test_a_category_missing_its_metadata_omits_the_heading_rather_than_printing_empty():
    page = render([_category(why_it_grows="")])
    assert "**Why it grows.**" not in page
    assert "**What it contains.**" in page


def test_every_registered_category_is_rendered():
    categories = get_all_categories()
    page = render(categories)
    assert page.count("### ") == len(categories)
    for category in categories:
        assert f"`{category.id}`" in page, f"{category.id} missing from the catalogue"


@pytest.mark.parametrize("field", ["what_it_contains", "why_safe_to_delete"])
def test_registered_categories_carry_the_metadata_the_catalogue_publishes(field):
    missing = [c.id for c in get_all_categories() if not (getattr(c, field, "") or "").strip()]
    assert not missing, f"categories with no {field}: {missing}"


def test_writes_the_file_it_is_given(tmp_path):
    destination = tmp_path / "nested" / "categories.md"
    assert main(["--output", str(destination)]) == 0
    assert destination.read_text(encoding="utf-8").startswith("# Cleanup catalogue")
