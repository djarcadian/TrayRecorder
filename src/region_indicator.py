"""Persistent visual indicators while a custom-region recording is active:

- BorderOverlay: thin dotted outline drawn JUST OUTSIDE the recorded rect
  (so it never appears in the captured video). Click-through.
- StopButton: small floating button placed outside the rect.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QPushButton, QWidget


_STOP_BUTTON_STYLE = """
QPushButton {
    background-color: #d12d2d;
    color: white;
    border: 1px solid #f06060;
    border-radius: 6px;
    padding: 7px 14px;
    font: bold 13px 'Segoe UI';
}
QPushButton:hover { background-color: #e74040; }
QPushButton:pressed { background-color: #b02323; }
"""


class BorderOverlay(QWidget):
    """Thin dotted line tracing the recording region (click-through)."""

    def __init__(self, region: QRect) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        vd = QRect()
        for s in QGuiApplication.screens():
            vd = vd.united(s.geometry())
        self._vd = vd
        self._region = region
        self.setGeometry(vd)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        # Convert region (virtual-desktop coords) into widget-local coords
        # and inflate by 2 px so the line falls OUTSIDE the captured area.
        x = self._region.x() - self._vd.x() - 2
        y = self._region.y() - self._vd.y() - 2
        w = self._region.width() + 4
        h = self._region.height() + 4
        pen = QPen(QColor(255, 70, 70, 230))
        pen.setStyle(Qt.DashLine)
        pen.setWidth(2)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(x, y, w, h)


class StopButton(QWidget):
    """Floating ■ Stop button anchored just outside the recording region."""

    clicked = Signal()

    def __init__(self, region: QRect) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self._btn = QPushButton("■ Stop", self)
        self._btn.setStyleSheet(_STOP_BUTTON_STYLE)
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.clicked.connect(self.clicked)
        self._btn.adjustSize()
        self.resize(self._btn.size())

        # Default placement: below the region, right-aligned to the region.
        x = region.x() + region.width() - self.width()
        y = region.y() + region.height() + 6
        # Pick the screen the region is centered on for bounds checking.
        center_screen = QGuiApplication.screenAt(region.center())
        if center_screen is None:
            center_screen = QGuiApplication.primaryScreen()
        scr = center_screen.availableGeometry()

        # If below the region would fall off-screen, place above instead.
        if y + self.height() > scr.bottom() - 4:
            y = region.y() - self.height() - 6
            if y < scr.top() + 4:
                # Region fills screen; tuck the button into the bottom-right inside.
                y = scr.bottom() - self.height() - 4
                x = scr.right() - self.width() - 4
        # Horizontal clamp
        if x + self.width() > scr.right() - 4:
            x = scr.right() - self.width() - 4
        if x < scr.left() + 4:
            x = scr.left() + 4
        self.move(x, y)
