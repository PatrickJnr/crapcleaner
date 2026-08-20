"""Tests for the shared visual polish toolkit."""

from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication, QFrame, QPushButton

from crapcleaner.gui import effects
from crapcleaner.gui.effects import (
    SPARKLINE_CAPACITY,
    AnimatedNumber,
    SegmentedBar,
    Sparkline,
    add_depth,
    glow,
    motion_enabled,
)
from crapcleaner.gui.theme import THEMES
from crapcleaner.utils.format import format_size

_app = QApplication.instance() or QApplication(["test", "-platform", "offscreen"])


def test_animated_number_uses_its_formatter():
    label = AnimatedNumber(formatter=format_size)
    label.set_value(1024 * 1024 * 1024)
    assert "GB" in label.text()

    label.set_formatter(lambda v: f"{v:.1f}% Load")
    assert label.text().endswith("% Load")


def test_animated_number_lands_immediately_without_motion():
    """Reduce motion must mean the value arrives, not that it never arrives."""
    label = AnimatedNumber(formatter=lambda v: f"{v:.0f}")
    with patch.object(effects, "motion_enabled", return_value=False):
        label.animate_to(500)
    assert label.get_value() == 500
    assert label.text() == "500"


def test_animated_number_animates_when_motion_is_enabled():
    label = AnimatedNumber(formatter=lambda v: f"{v:.0f}")
    with patch.object(effects, "motion_enabled", return_value=True):
        label.animate_to(1000)
        # Mid-flight it has not arrived yet, but it is on its way from zero.
        assert label.get_value() < 1000
        label.stop()


def test_animated_number_stop_is_idempotent():
    label = AnimatedNumber()
    label.stop()
    label.stop()
    assert label.get_value() == 0


def test_motion_enabled_survives_a_settings_failure():
    """A settings problem must never stop the UI drawing."""
    with patch("crapcleaner.config.load_settings", side_effect=OSError("boom")):
        assert motion_enabled() is True


def test_sparkline_never_exceeds_capacity():
    spark = Sparkline(capacity=10)
    for i in range(500):
        spark.push(i)
    assert spark.sample_count() == 10


def test_sparkline_default_capacity():
    spark = Sparkline()
    for i in range(SPARKLINE_CAPACITY * 3):
        spark.push(i)
    assert spark.sample_count() == SPARKLINE_CAPACITY


def test_sparkline_clamps_negative_samples():
    spark = Sparkline()
    spark.push(-50)
    assert spark._samples[0] == 0.0


def test_sparkline_paints_without_error_in_every_theme(tmp_path):
    """A palette missing a token would raise here rather than in front of a user."""
    from PySide6.QtGui import QPixmap

    spark = Sparkline()
    for value in (10, 40, 90, 20, 60):
        spark.push(value)
    spark.resize(120, 26)
    for theme in THEMES:
        spark.apply_theme(theme)
        pixmap = QPixmap(spark.size())
        spark.render(pixmap)


def test_sparkline_with_too_few_samples_draws_nothing():
    from PySide6.QtGui import QPixmap

    spark = Sparkline()
    spark.resize(120, 26)
    spark.render(QPixmap(spark.size()))  # zero samples
    spark.push(5)
    spark.render(QPixmap(spark.size()))  # one sample
    assert spark.sample_count() == 1


def test_sparkline_clear():
    spark = Sparkline()
    for value in range(10):
        spark.push(value)
    spark.clear()
    assert spark.sample_count() == 0


def test_segmented_bar_proportions_sum_to_one():
    bar = SegmentedBar()
    bar.set_segments([("a", 803.0, "danger"), ("b", 12.0, "review"), ("c", 127.5, "safe")])
    shares = bar.proportions()
    assert len(shares) == 3
    assert sum(shares) == pytest.approx(1.0)
    assert shares[0] > shares[2] > shares[1]


def test_segmented_bar_handles_degenerate_input():
    """No data and all-zero data must not divide by zero."""
    bar = SegmentedBar()
    bar.set_segments([])
    assert bar.proportions() == []

    bar.set_segments([("a", 0, "safe"), ("b", 0, "safe")])
    assert bar.proportions() == []


def test_segmented_bar_single_segment_takes_everything():
    bar = SegmentedBar()
    bar.set_segments([("only", 42.0, "accent")])
    assert bar.proportions() == [pytest.approx(1.0)]


def test_segmented_bar_fills_immediately_without_motion():
    bar = SegmentedBar()
    with patch.object(effects, "motion_enabled", return_value=False):
        bar.set_segments([("a", 1.0, "safe")])
    assert bar.get_fill() == 1.0


def test_segmented_bar_fill_is_clamped():
    bar = SegmentedBar()
    bar.set_fill(5.0)
    assert bar.get_fill() == 1.0
    bar.set_fill(-5.0)
    assert bar.get_fill() == 0.0


def test_segmented_bar_paints_in_every_theme():
    from PySide6.QtGui import QPixmap

    bar = SegmentedBar()
    bar.resize(200, 12)
    bar.set_segments([("a", 3.0, "safe"), ("b", 1.0, "review"), ("c", 2.0, "danger")])
    for theme in THEMES:
        bar.apply_theme(theme)
        bar.render(QPixmap(bar.size()))


def test_segmented_bar_muted_mode_still_paints():
    from PySide6.QtGui import QPixmap

    bar = SegmentedBar()
    bar.resize(200, 12)
    bar.set_segments([("a", 1.0, "faint"), ("b", 1.0, "faint")], muted=True)
    bar.render(QPixmap(bar.size()))
    assert bar.proportions() == [pytest.approx(0.5), pytest.approx(0.5)]


def test_add_depth_card_level_avoids_the_effect_graph():
    """Repeating widgets must not each carry an offscreen-rendered effect."""
    card = QFrame()
    add_depth(card, "dark", "card")
    assert card.graphicsEffect() is None


def test_add_depth_hero_level_applies_a_shadow():
    hero = QFrame()
    add_depth(hero, "dark", "hero")
    assert hero.graphicsEffect() is not None


def test_hover_toggles_the_stylesheet_property():
    from PySide6.QtCore import QEvent

    card = QFrame()
    add_depth(card, "dark", "card")
    QApplication.sendEvent(card, QEvent(QEvent.Type.Enter))
    assert card.property("hovered") == "true"
    QApplication.sendEvent(card, QEvent(QEvent.Type.Leave))
    assert card.property("hovered") == "false"


def test_glow_applies_to_a_button():
    button = QPushButton("Scan")
    glow(button, "dark")
    assert button.graphicsEffect() is not None


def test_depth_helpers_work_in_every_theme():
    for theme in THEMES:
        add_depth(QFrame(), theme, "hero")
        glow(QPushButton("x"), theme)
