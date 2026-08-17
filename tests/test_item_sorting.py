"""Sorting items must not recurse into their own __lt__ via super() (PySide6)."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidget, QTreeWidget

from crapcleaner.gui.views import NumericItem, _SizeSortedItem

_app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])


def test_numeric_item_sorts_text_column_without_recursion():
    table = QTableWidget(3, 1)
    for row, text in enumerate(["banana", "apple", "cherry"]):
        table.setItem(row, 0, NumericItem(text))
    table.sortItems(0, Qt.SortOrder.AscendingOrder)
    assert [table.item(r, 0).text() for r in range(3)] == ["apple", "banana", "cherry"]


def test_numeric_item_sorts_by_stored_value():
    table = QTableWidget(3, 1)
    for row, (text, value) in enumerate([("1 GB", 1024), ("2 MB", 2), ("500 KB", 0.5)]):
        table.setItem(row, 0, NumericItem(text, value))
    table.sortItems(0, Qt.SortOrder.AscendingOrder)
    assert [table.item(r, 0).text() for r in range(3)] == ["500 KB", "2 MB", "1 GB"]


def test_size_sorted_item_sorts_name_and_size_columns():
    tree = QTreeWidget()
    tree.setColumnCount(4)
    for name, size in [("beta", 10), ("alpha", 30), ("gamma", 20)]:
        item = _SizeSortedItem([name, "", "", ""])
        item.set_sort_size(size)
        tree.addTopLevelItem(item)

    tree.sortItems(0, Qt.SortOrder.AscendingOrder)
    assert [tree.topLevelItem(i).text(0) for i in range(3)] == ["alpha", "beta", "gamma"]

    tree.sortItems(3, Qt.SortOrder.AscendingOrder)
    assert [tree.topLevelItem(i).text(0) for i in range(3)] == ["beta", "gamma", "alpha"]
