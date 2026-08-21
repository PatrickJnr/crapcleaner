"""The nav badge is a pill beside the label, not part of it.

Appending the count to the button text meant a growing label inside a fixed-width
rail, with no way to align or colour the number.
"""

from PySide6.QtWidgets import QApplication, QWidget

from crapcleaner.gui.sidebar import NAV_ITEMS, NAV_SECTIONS, NavButton, Sidebar

_app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])


def _sidebar() -> Sidebar:
    return Sidebar("1.2.1")


def test_a_badge_leaves_the_label_alone():
    bar = _sidebar()
    button = bar._buttons["cleanup"]
    label_before = button.text()

    bar.set_badge("cleanup", "1.2 GB")

    assert button.text() == label_before
    assert button._badge.text() == "1.2 GB"


def test_an_empty_badge_hides_the_pill():
    bar = _sidebar()
    bar.set_badge("drives", "5")
    bar.set_badge("drives", "")

    assert bar._buttons["drives"]._badge.isHidden()


def test_an_attention_badge_is_marked_for_the_stylesheet():
    bar = _sidebar()
    bar.set_badge("updates", "2", "accent")
    bar.set_badge("drives", "5")

    assert bar._buttons["updates"]._badge.property("level") == "accent"
    assert bar._buttons["drives"]._badge.property("level") == ""


def test_a_single_digit_still_forms_a_pill():
    """Narrower than twice the corner radius and the pill renders as a square."""
    bar = _sidebar()
    bar.set_badge("updates", "2", "accent")
    bar.show()
    _app.processEvents()

    badge = bar._buttons["updates"]._badge
    assert badge.width() >= 20
    assert badge.height() == 18
    bar.close()


def test_the_count_reaches_assistive_technology():
    bar = _sidebar()
    bar.set_badge("updates", "2", "accent")

    assert "2" in bar._buttons["updates"].accessibleDescription()


def test_no_two_nav_items_share_an_icon():
    """App Updates and System Updates sat next to each other under the same glyph."""
    icons = [icon_name for _, _, icon_name in NAV_ITEMS]

    assert len(icons) == len(set(icons))


# --- layout -------------------------------------------------------------------


def test_no_group_is_long_enough_to_lose_your_place():
    """Eight items under SYSTEM was one undifferentiated run down half the rail."""
    for title, items in NAV_SECTIONS:
        assert len(items) <= 4, f"{title} has {len(items)} items"


def test_the_rail_fits_the_smallest_window_the_app_allows():
    """Nav buttons are a fixed height, so a rail taller than the window is simply cut off."""
    from crapcleaner.gui.app import MainWindow

    bar = _sidebar()
    _minimum_width, minimum_height = MainWindow.MINIMUM_SIZE

    assert bar.minimumSizeHint().height() < minimum_height


def test_a_badge_stays_inside_the_rail():
    """A long label used to push its button wider than the rail, clipping the badge."""
    bar = _sidebar()
    bar.set_badge("cleanup", "1.2 GB", "accent")
    bar.resize(230, 620)
    bar.show()
    _app.processEvents()

    button = bar._buttons["cleanup"]
    right_edge = button.mapTo(bar, button._badge.geometry().topRight()).x()

    assert right_edge <= bar.width()
    bar.close()


def test_the_scrolling_wrapper_does_not_restyle_what_it_holds():
    """A selector-less widget stylesheet applies to the whole subtree, and blanked both
    the active row's fill and every badge pill."""
    bar = _sidebar()

    for child in bar.findChildren(QWidget):
        sheet = child.styleSheet()
        if "background" in sheet and child.findChildren(NavButton):
            assert "#" in sheet or "{" in sheet, f"unscoped stylesheet on {child}: {sheet!r}"
