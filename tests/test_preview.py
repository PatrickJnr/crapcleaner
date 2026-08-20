"""Unit tests for the pre-cleanup preview engine."""

import os

from crapcleaner.core.preview import generate_cleanup_preview
from crapcleaner.models.category import CacheTarget, CleanupCategory, SafetyLevel


def test_generate_cleanup_preview(tmp_path):
    f1 = tmp_path / "temp1.tmp"
    f2 = tmp_path / "temp2.tmp"
    f1.write_bytes(b"1" * 100)
    f2.write_bytes(b"2" * 200)

    category = CleanupCategory(
        id="test_preview_cat",
        name="Test Preview Category",
        description="A test preview category",
        safety_level=SafetyLevel.SAFE,
        group="Test",
        targets=[CacheTarget(path=str(tmp_path))],
    )

    preview = generate_cleanup_preview([category])
    assert preview is not None
    assert preview.total_estimated_size >= 300
    assert preview.total_item_count >= 2
    assert len(preview.categories) == 1

    d = preview.to_dict()
    assert "total_estimated_size" in d
    assert "categories" in d
    assert len(d["categories"]) == 1

    assert not preview.check_staleness()
    f1.unlink()
    assert preview.check_staleness() is True
    assert preview.is_stale is True


class TestStaleness:
    """`check_staleness` was never called, so `is_stale` shipped as a hardcoded False."""

    def _finder_category(self, victim, cid="finder_cat"):
        def finder():
            os.remove(victim)
            return []

        return CleanupCategory(
            id=cid,
            name="Finder category",
            description="desc",
            safety_level=SafetyLevel.SAFE,
            group="Test",
            finder=finder,
        )

    def test_a_file_that_vanishes_during_the_walk_marks_the_preview_stale(self, tmp_path):
        listed = tmp_path / "listed" / "temp.tmp"
        listed.parent.mkdir()
        listed.write_bytes(b"x" * 100)
        first = CleanupCategory(
            id="dir_cat",
            name="Directory category",
            description="desc",
            safety_level=SafetyLevel.SAFE,
            group="Test",
            targets=[CacheTarget(path=str(listed.parent))],
        )

        preview = generate_cleanup_preview(
            [first, self._finder_category(str(listed))], resolve_finders=True
        )

        assert preview.is_stale is True
        assert preview.to_dict()["is_stale"] is True
        assert preview.categories[0].items[0].exists is False

    def test_an_intact_preview_is_not_stale(self, tmp_path):
        (tmp_path / "temp.tmp").write_bytes(b"x" * 100)
        category = CleanupCategory(
            id="dir_cat",
            name="Directory category",
            description="desc",
            safety_level=SafetyLevel.SAFE,
            group="Test",
            targets=[CacheTarget(path=str(tmp_path))],
        )

        assert generate_cleanup_preview([category]).is_stale is False

    def test_an_action_label_is_not_mistaken_for_a_missing_file(self):
        category = CleanupCategory(
            id="action_cat",
            name="Action category",
            description="desc",
            safety_level=SafetyLevel.SAFE,
            group="Test",
            action="dism_component_cleanup",
        )

        assert generate_cleanup_preview([category]).is_stale is False
