"""Reusable visual polish: animated values, sparklines, segmented bars, depth.

Every colour here resolves from a palette token, so all 43 themes work without any
per-theme code, and every animation checks the *Reduce motion* preference and snaps
straight to its final value when motion is switched off.

Depth is deliberately split. Widgets that repeat inside a scroll area are painted,
because ``QGraphicsEffect`` renders through an offscreen pixmap that disables subpixel
text antialiasing and costs a repaint per instance. A real drop shadow is reserved for
hero surfaces, where there is only one.
"""

from collections import deque

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QLabel, QWidget

from crapcleaner.gui.theme import color as theme_color

#: How many samples a vitals sparkline keeps. At the dashboard's tick rate this is
#: roughly a minute of history.
SPARKLINE_CAPACITY = 60

_DEFAULT_DURATION = 420


def motion_enabled() -> bool:
    """Whether animations should run, honouring the Reduce motion preference."""
    try:
        from crapcleaner.config import load_settings

        return not bool(load_settings().get("reduce_motion", False))
    except Exception:
        # A settings failure must never stop the UI from drawing.
        return True


def _c(theme: str, token: str) -> str:
    return theme_color(theme, token)


def _qcolor(theme: str, token: str, alpha: int | None = None) -> QColor:
    color = QColor(_c(theme, token))
    if alpha is not None:
        color.setAlpha(alpha)
    return color


class AnimatedNumber(QLabel):
    """A label whose value eases to each new target instead of snapping.

    The formatter turns the raw number into display text, so one widget serves byte
    counts, percentages, and plain totals::

        AnimatedNumber(formatter=format_size)
        AnimatedNumber(formatter=lambda v: f"{v:.1f}% Load")
    """

    def __init__(self, formatter=None, duration: int = _DEFAULT_DURATION, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self._formatter = formatter or (lambda v: f"{v:,.0f}")
        self._duration = duration
        self._animation: QPropertyAnimation | None = None
        self.setText(self._formatter(0.0))

    def get_value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        self._value = float(value)
        self.setText(self._formatter(self._value))

    #: Animating a Qt property rather than a QGraphicsEffect keeps text crisp.
    value = Property(float, get_value, set_value)

    def set_formatter(self, formatter) -> None:
        self._formatter = formatter
        self.setText(self._formatter(self._value))

    def animate_to(self, target: float) -> None:
        """Ease to `target`, or land on it immediately when motion is disabled."""
        target = float(target)
        self.stop()

        if not motion_enabled() or abs(target - self._value) < 0.01:
            self.set_value(target)
            return

        animation = QPropertyAnimation(self, b"value", self)
        animation.setDuration(self._duration)
        animation.setStartValue(self._value)
        animation.setEndValue(target)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda: setattr(self, "_animation", None))
        self._animation = animation
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def stop(self) -> None:
        if self._animation is not None:
            self._animation.stop()
            self._animation = None


class Sparkline(QWidget):
    """A compact history strip fed by whatever already samples the metric.

    It owns no timer: the caller pushes a sample whenever it has one, which keeps the
    dashboard on a single tick instead of one per card.
    """

    def __init__(
        self,
        theme: str = "dark",
        token: str = "accent",
        capacity: int = SPARKLINE_CAPACITY,
        parent=None,
    ):
        super().__init__(parent)
        self._theme = theme
        self._token = token
        self._samples: deque[float] = deque(maxlen=max(2, capacity))
        self._ceiling = 100.0
        self.setFixedHeight(26)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def push(self, value: float) -> None:
        self._samples.append(max(0.0, float(value)))
        self.update()

    def set_ceiling(self, ceiling: float) -> None:
        """Fix the vertical scale. Percentages use 100; rates auto-scale when None."""
        self._ceiling = float(ceiling) if ceiling else 0.0
        self.update()

    def clear(self) -> None:
        self._samples.clear()
        self.update()

    def sample_count(self) -> int:
        return len(self._samples)

    def apply_theme(self, theme: str) -> None:
        self._theme = theme
        self.update()

    def _scale(self) -> float:
        if self._ceiling:
            return self._ceiling
        peak = max(self._samples) if self._samples else 0.0
        return peak if peak > 0 else 1.0

    def paintEvent(self, event):  # noqa: N802 - Qt naming
        if len(self._samples) < 2:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect().adjusted(0, 2, 0, -2)
        scale = self._scale()
        step = rect.width() / (len(self._samples) - 1)

        points: list[QPointF] = []
        for index, sample in enumerate(self._samples):
            ratio = min(1.0, sample / scale) if scale else 0.0
            x = rect.left() + index * step
            y = rect.bottom() - ratio * rect.height()
            points.append(QPointF(x, y))

        # Filled area first, so the stroke sits on top of its own gradient-free wash.
        area = QPainterPath()
        area.moveTo(QPointF(points[0].x(), rect.bottom()))
        for point in points:
            area.lineTo(point)
        area.lineTo(QPointF(points[-1].x(), rect.bottom()))
        area.closeSubpath()
        painter.fillPath(area, _qcolor(self._theme, self._token, 46))

        stroke = QPainterPath()
        stroke.moveTo(points[0])
        for point in points[1:]:
            stroke.lineTo(point)
        painter.setPen(QPen(_qcolor(self._theme, self._token), 1.6))
        painter.drawPath(stroke)

        # A dot on the newest sample makes the direction of travel readable at a glance.
        painter.setBrush(_qcolor(self._theme, self._token))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(points[-1], 2.0, 2.0)
        painter.end()


class SegmentedBar(QWidget):
    """A proportional bar split into labelled segments.

    Segments are ``(label, value, token)`` triples. Values are normalised, so callers
    pass raw byte counts rather than percentages.
    """

    def __init__(self, theme: str = "dark", height: int = 10, radius: int = 5, parent=None):
        super().__init__(parent)
        self._theme = theme
        self._segments: list[tuple[str, float, str]] = []
        self._radius = radius
        self._fill = 0.0
        self._animation: QPropertyAnimation | None = None
        self._muted = False
        self.setFixedHeight(height)

    def get_fill(self) -> float:
        return self._fill

    def set_fill(self, value: float) -> None:
        self._fill = max(0.0, min(1.0, float(value)))
        self.update()

    fill = Property(float, get_fill, set_fill)

    def set_segments(self, segments, muted: bool = False) -> None:
        """Replace the segments and sweep the bar in.

        `muted` draws the same shape in the faint token, for the pre-scan state where the
        categories are known but their sizes are not.
        """
        self._segments = [(str(a), max(0.0, float(b)), str(c)) for a, b, c in segments]
        self._muted = bool(muted)

        if self._animation is not None:
            self._animation.stop()
            self._animation = None

        if not motion_enabled():
            self.set_fill(1.0)
            return

        animation = QPropertyAnimation(self, b"fill", self)
        animation.setDuration(520)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda: setattr(self, "_animation", None))
        self._animation = animation
        animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def proportions(self) -> list[float]:
        """Each segment's share of the total, summing to 1.0 (empty when there is no data)."""
        total = sum(value for _label, value, _token in self._segments)
        if total <= 0:
            return []
        return [value / total for _label, value, _token in self._segments]

    def apply_theme(self, theme: str) -> None:
        self._theme = theme
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)

        rect = QRectF(self.rect())
        track = QPainterPath()
        track.addRoundedRect(rect, self._radius, self._radius)
        painter.fillPath(track, _qcolor(self._theme, "surface2"))

        shares = self.proportions()
        if not shares:
            painter.end()
            return

        # Clip to the rounded track so segments inherit its corners.
        painter.setClipPath(track)

        x = rect.left()
        width = rect.width() * self._fill
        for share, (_label, _value, token) in zip(shares, self._segments):
            segment_width = width * share
            if segment_width <= 0:
                continue
            color = _qcolor(self._theme, "faint" if self._muted else token)
            painter.fillRect(QRectF(x, rect.top(), segment_width, rect.height()), color)
            x += segment_width
        painter.end()


class HoverLift(QWidget):
    """Event filter giving a widget a subtle raise and accent border on hover.

    Installed by :func:`add_depth`. The lift is a stylesheet property toggle rather than a
    geometry change, so it cannot disturb the layout of the row it sits in.
    """

    def __init__(self, target: QWidget):
        super().__init__(target)
        self._target = target
        target.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        target.installEventFilter(self)

    def eventFilter(self, watched, event):  # noqa: N802 - Qt naming
        from PySide6.QtCore import QEvent

        if watched is self._target:
            if event.type() == QEvent.Type.Enter:
                self._target.setProperty("hovered", "true")
                self._repolish()
            elif event.type() == QEvent.Type.Leave:
                self._target.setProperty("hovered", "false")
                self._repolish()
        return False

    def _repolish(self) -> None:
        style = self._target.style()
        style.unpolish(self._target)
        style.polish(self._target)


def add_depth(widget: QWidget, theme: str = "dark", level: str = "card") -> QWidget:
    """Give `widget` depth.

    Named `add_depth` rather than `elevate` because `utils.platform.elevate` already
    means "escalate to administrator" throughout this codebase.

    ``level="card"`` is the cheap path for widgets that repeat: a hover lift driven by a
    stylesheet property, no effect graph involved. ``level="hero"`` adds a real drop
    shadow and is intended for the one or two headline surfaces on a page.
    """
    HoverLift(widget)

    if level == "hero":
        shadow = QGraphicsDropShadowEffect(widget)
        shadow.setBlurRadius(28)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(_qcolor(theme, "window", 160))
        widget.setGraphicsEffect(shadow)

    return widget


def glow(widget: QWidget, theme: str = "dark") -> QWidget:
    """Put an accent halo behind a primary action."""
    halo = QGraphicsDropShadowEffect(widget)
    halo.setBlurRadius(24)
    halo.setXOffset(0)
    halo.setYOffset(0)
    halo.setColor(_qcolor(theme, "accent", 120))
    widget.setGraphicsEffect(halo)
    return widget
