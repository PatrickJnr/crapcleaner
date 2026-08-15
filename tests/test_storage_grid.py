"""Storage grid layout, navigation, and scaling behaviour."""

import pytest

from crapcleaner.storage.analyzer import StorageNode


@pytest.fixture
def qt_app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _node(name, size, children=(), path=""):
    node = StorageNode(name=name, path=path or f"C:/{name}", size=size)
    node.children = list(children)
    return node


def _grid(qt_app, node, width=800, height=600):
    from crapcleaner.gui.views import StorageGrid

    grid = StorageGrid("dark")
    grid.resize(width, height)
    grid.set_node(node)
    return grid


def test_empty_dataset_lays_out_nothing(qt_app):
    grid = _grid(qt_app, _node("empty", 0))
    assert grid._cells == []
    assert grid.selected_cell() is None


def test_none_node_is_safe(qt_app):
    grid = _grid(qt_app, None)
    assert grid._cells == []


def test_small_dataset_cell_area_is_proportional(qt_app):
    root = _node("root", 100, [_node("big", 75), _node("small", 25)])
    grid = _grid(qt_app, root)
    areas = {c.label: c.rect.width() * c.rect.height() for c in grid._cells}
    assert areas["big"] > areas["small"] * 2.5
    assert grid._cells[0].label == "big"


def test_cells_stay_inside_the_widget_and_do_not_overlap(qt_app):
    children = [_node(f"d{i}", (i + 1) * 1000) for i in range(12)]
    grid = _grid(qt_app, _node("root", sum(c.size for c in children), children))
    bounds = grid.rect()
    for cell in grid._cells:
        assert bounds.contains(cell.rect.toRect().intersected(bounds))
    for i, a in enumerate(grid._cells):
        for b in grid._cells[i + 1 :]:
            overlap = a.rect.intersected(b.rect)
            assert overlap.width() < 1.5 or overlap.height() < 1.5


def test_layout_covers_the_available_area(qt_app):
    children = [_node(f"d{i}", 1000 * (i + 1)) for i in range(8)]
    grid = _grid(qt_app, _node("root", sum(c.size for c in children), children))
    covered = sum(c.rect.width() * c.rect.height() for c in grid._cells)
    total = (grid.width() - 4) * (grid.height() - 4)
    assert covered == pytest.approx(total, rel=0.02)


def test_direct_files_are_shown_as_their_own_cell(qt_app):
    root = _node("root", 1000, [_node("child", 400)])
    grid = _grid(qt_app, root)
    labels = [c.label for c in grid._cells]
    assert "Files in this folder" in labels
    remainder = next(c for c in grid._cells if c.label == "Files in this folder")
    assert remainder.size == 600
    assert remainder.drillable is False


def test_very_large_dataset_is_capped_and_aggregated(qt_app):
    children = [_node(f"d{i}", 5000 - i) for i in range(4000)]
    root = _node("root", sum(c.size for c in children), children)
    grid = _grid(qt_app, root)
    assert len(grid._cells) <= StorageGridCap() + 1
    other = [c for c in grid._cells if c.label.startswith("Other (")]
    assert other and other[0].drillable is False
    assert sum(c.size for c in grid._cells) == root.size


def StorageGridCap():
    from crapcleaner.gui.views import StorageGrid

    return StorageGrid._MAX_CELLS


def test_medium_dataset_keeps_every_child(qt_app):
    children = [_node(f"d{i}", 100 + i) for i in range(25)]
    grid = _grid(qt_app, _node("root", sum(c.size for c in children), children))
    assert len(grid._cells) == 25


def test_keyboard_selection_moves_and_stays_in_range(qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

    children = [_node(f"d{i}", 1000 - i * 10) for i in range(5)]
    grid = _grid(qt_app, _node("root", sum(c.size for c in children), children))

    def press(key):
        grid.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))

    assert grid.selected_cell().label == "d0"
    press(Qt.Key.Key_Right)
    assert grid.selected_cell().label == "d1"
    press(Qt.Key.Key_Left)
    press(Qt.Key.Key_Left)
    assert grid.selected_cell().label == "d0"
    press(Qt.Key.Key_End)
    assert grid._selected == len(grid._cells) - 1
    press(Qt.Key.Key_End)
    assert grid._selected == len(grid._cells) - 1


def test_enter_activates_only_drillable_cells(qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

    root = _node("root", 1000, [_node("child", 1000, [_node("leaf", 1000)])])
    grid = _grid(qt_app, root)
    activated = []
    grid.activated.connect(activated.append)
    grid.keyPressEvent(
        QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    )
    assert [n.name for n in activated] == ["child"]


def test_resize_relayouts_without_losing_cells(qt_app):
    children = [_node(f"d{i}", 500 * (i + 1)) for i in range(6)]
    grid = _grid(qt_app, _node("root", sum(c.size for c in children), children))
    before = len(grid._cells)
    grid.resize(400, 300)
    grid._relayout()
    assert len(grid._cells) == before
    assert all(c.rect.width() >= 0 and c.rect.height() >= 0 for c in grid._cells)


def test_view_drill_down_and_back(qt_app):
    from unittest.mock import MagicMock

    from crapcleaner.gui.views import StorageBreakdownView

    view = StorageBreakdownView(MagicMock())
    leaf = _node("leaf", 500)
    child = _node("child", 900, [leaf])
    root = _node("root", 1000, [child])
    view._populate_tree(root)

    assert view.storage_grid.node() is root
    assert view.grid_up_btn.isEnabled() is False

    view.grid_navigate_into(child)
    assert view.storage_grid.node() is child
    assert view.grid_up_btn.isEnabled() is True
    assert "child" in view.grid_path_label.text()

    view.grid_navigate_up()
    assert view.storage_grid.node() is root
    assert view.grid_up_btn.isEnabled() is False


def test_view_selection_detail_reports_size_and_share(qt_app):
    from unittest.mock import MagicMock

    from crapcleaner.gui.views import StorageBreakdownView

    view = StorageBreakdownView(MagicMock())
    view._populate_tree(_node("root", 1000, [_node("a", 750), _node("b", 250)]))
    view._on_grid_selection(view.storage_grid.selected_cell())
    assert "75.0%" in view.grid_detail_label.text()
