"""Unit tests for the pre-cleanup preview engine."""

from crapcleaner.cleaners.preview import generate_cleanup_preview
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

    # Test staleness check
    assert not preview.check_staleness()
    # Delete a file and check staleness
    f1.unlink()
    assert preview.check_staleness() is True
    assert preview.is_stale is True
