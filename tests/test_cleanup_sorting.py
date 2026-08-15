"""Cleanup category sorting and cleanup-result classification."""

import pytest

from crapcleaner.models.report import CleanupReport, CleanupResult


@pytest.fixture
def cleanup_view():
    from PySide6.QtWidgets import QApplication

    from crapcleaner.gui.views import CleanupView

    QApplication.instance() or QApplication([])

    class DummyMain:
        def __getattr__(self, name):
            return lambda *args, **kwargs: None

    return CleanupView(DummyMain())


def _sized_categories():
    from crapcleaner.registry import get_all_categories

    categories = get_all_categories()[:10]
    for index, category in enumerate(categories):
        category.group = "Test Group"
        category.size = (index * 7 % 5) * 1024**3
        category.item_count = index
    return categories


def _child_sizes(view):
    from PySide6.QtCore import Qt

    group = view.tree.topLevelItem(0)
    return [
        group.child(i).data(0, Qt.ItemDataRole.UserRole).size for i in range(group.childCount())
    ]


def test_categories_sort_by_reclaimable_size(cleanup_view):
    cleanup_view.populate(_sized_categories())
    cleanup_view.update_sizes()

    cleanup_view.sort_by_size(True)
    sizes = _child_sizes(cleanup_view)
    assert sizes == sorted(sizes, reverse=True)

    cleanup_view.sort_by_size(False)
    sizes = _child_sizes(cleanup_view)
    assert sizes == sorted(sizes)


def test_size_sort_is_numeric_not_alphabetical(cleanup_view):
    categories = _sized_categories()
    categories[0].size = 900 * 1024**2
    categories[1].size = 5 * 1024**3
    cleanup_view.populate(categories)
    cleanup_view.update_sizes()
    cleanup_view.sort_by_size(True)
    assert _child_sizes(cleanup_view)[0] == 5 * 1024**3


def test_report_separates_permission_failures_from_errors():
    report = CleanupReport(started=__import__("datetime").datetime.now())
    report.results.append(
        CleanupResult(
            category_id="x",
            category_name="X",
            files_deleted=1,
            space_recovered=10,
            skipped=2,
            errors=["disk error"],
            permission_errors=["C:/locked: Access is denied"],
            skip_reasons=["C:/held: in use or locked by another process"],
        )
    )
    assert report.permission_errors == ["C:/locked: Access is denied"]
    assert report.skip_reasons == ["C:/held: in use or locked by another process"]
    assert report.to_dict()["permission_errors"] == ["C:/locked: Access is denied"]


def test_protected_paths_are_skips_not_errors(tmp_path, monkeypatch):
    from crapcleaner.cleaners import cleaner as cleaner_mod

    monkeypatch.setattr(cleaner_mod, "validate_cleanup_path", lambda path: (False, "protected"))
    result = cleaner_mod._delete_target_files(str(tmp_path), (), True, False, True, None, False)
    deleted, recovered, skipped, errors, permission_errors, skip_reasons = result
    assert errors == []
    assert permission_errors == []
    assert skip_reasons == ["protected"]
