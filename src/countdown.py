"""3-2-1 countdown overlay centered on a specific monitor."""

from __future__ import annotations

from PySide6.QtCore import Qt, QRect, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QScreen
from PySide6.QtWidgets import QWidget


class CountdownOverlay(QWidget):
    finished = Signal()

    def __init__(self, screen: QScreen, seconds: int) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setGeometry(screen.geometry())
        self._remaining = max(1, int(seconds))
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _tick(self) -> None:
        self._remaining -= 1
        if self._remaining <= 0:
            self._timer.stop()
            self.finished.emit()
            self.close()
        else:
            self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        size = min(rect.width(), rect.height()) // 3
        box = QRect(0, 0, size, size)
        box.moveCenter(rect.center())
        p.setBrush(QColor(0, 0, 0, 200))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(box, 40, 40)
        font = QFont("Segoe UI", size // 2)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(255, 70, 70, 240))
        p.drawText(box, Qt.AlignCenter, str(self._remaining))
