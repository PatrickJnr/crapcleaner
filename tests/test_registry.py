"""Tests for the category registry."""

from crapcleaner.models.category import SafetyLevel
from crapcleaner.registry import (
    find_categories,
    get_all_categories,
    get_category_by_name,
    group_categories,
)


class TestRegistry:
    def test_returns_categories(self):
        cats = get_all_categories()
        assert len(cats) > 0
        assert all(c.id and c.name and c.group for c in cats)

    def test_has_dangerous_safety(self):
        cats = get_all_categories()
        assert any(c.safety_level == SafetyLevel.DANGEROUS for c in cats)

    def test_get_by_name(self):
        cats = get_all_categories()
        target = cats[0]
        found = get_category_by_name(target.name)
        assert found.id == target.id

    def test_get_by_name_missing(self):
        import pytest

        with pytest.raises(KeyError):
            get_category_by_name("Does Not Exist 12345")

    def test_find_categories_substring(self):
        found = find_categories("cache")
        assert all("cache" in c.name.lower() or "cache" in c.id.lower() for c in found)
        assert len(found) > 0

    def test_group_categories(self):
        cats = get_all_categories()
        groups = group_categories(cats)
        assert sum(len(v) for v in groups.values()) == len(cats)
        assert "Windows" in groups

    def test_all_category_ids_are_unique(self):
        cats = get_all_categories()
        cat_ids = [c.id for c in cats]
        duplicates = [cid for cid in set(cat_ids) if cat_ids.count(cid) > 1]
        assert len(cat_ids) == len(set(cat_ids)), f"Duplicate category IDs found: {duplicates}"
