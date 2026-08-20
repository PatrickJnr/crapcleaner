"""Storage snapshots: what a comparison may and may not subtract."""

import pytest

from crapcleaner.analysis import snapshots
from crapcleaner.utils.disk_size import SIZE_ALLOCATED, SIZE_LOGICAL


@pytest.fixture
def config_home(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshots, "snapshot_dir", lambda: str(tmp_path / "snaps"))
    return tmp_path


class TestSizeModeMismatch:
    """BUG-05: the stored size_mode was written and never read, so a unit change
    between an allocated scan and a logical snapshot was reported as growth."""

    def _stored(self, root, size_mode):
        snapshots.save_snapshot(root, {root: 100 * 1024 * 1024}, size_mode=size_mode)

    def test_a_different_mode_is_refused_with_an_explanation(self, config_home):
        root = str(config_home)
        self._stored(root, SIZE_LOGICAL)

        comparison = snapshots.compare(root, {root: 180 * 1024 * 1024}, size_mode=SIZE_ALLOCATED)

        assert comparison is not None
        assert comparison.incomparable
        assert SIZE_LOGICAL in comparison.incomparable
        assert comparison.changes == []
        assert comparison.total_delta == 0

    def test_the_same_mode_still_compares(self, config_home):
        root = str(config_home)
        self._stored(root, SIZE_ALLOCATED)

        comparison = snapshots.compare(root, {root: 180 * 1024 * 1024}, size_mode=SIZE_ALLOCATED)

        assert comparison is not None
        assert not comparison.incomparable
        assert comparison.total_delta == 80 * 1024 * 1024

    def test_a_snapshot_predating_the_field_reads_as_logical(self, config_home):
        root = str(config_home)
        comparison = snapshots.compare(
            root,
            {root: 180 * 1024 * 1024},
            previous={"dirs": {root: 100 * 1024 * 1024}, "total": 100 * 1024 * 1024},
        )

        assert comparison is not None
        assert not comparison.incomparable

    def test_the_refusal_survives_serialisation(self, config_home):
        root = str(config_home)
        self._stored(root, SIZE_LOGICAL)

        payload = snapshots.compare(
            root, {root: 180 * 1024 * 1024}, size_mode=SIZE_ALLOCATED
        ).to_dict()

        assert payload["incomparable"]
        assert payload["total_delta"] == 0
