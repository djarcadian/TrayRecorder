"""Monitor enumeration + big-number identification overlays."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt, QRect, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QScreen
from PySide6.QtWidgets import QWidget


@dataclass(frozen=True)
class MonitorInfo:
    index: int
    name: str
    geometry: QRect
    device_pixel_ratio: float

    @property
    def width_px(self) -> int:
        return int(self.geometry.width() * self.device_pixel_ratio)

    @property
    def height_px(self) -> int:
        return int(self.geometry.height() * self.device_pixel_ratio)

    @property
    def offset_x_px(self) -> int:
        return int(self.geometry.x() * self.device_pixel_ratio)

    @property
    def offset_y_px(self) -> int:
        return int(self.geometry.y() * self.device_pixel_ratio)


def enumerate_monitors() -> list[MonitorInfo]:
    out: list[MonitorInfo] = []
    for i, screen in enumerate(QGuiApplication.screens()):
        out.append(
            MonitorInfo(
                index=i + 1,
                name=screen.name(),
                geometry=screen.geometry(),
                device_pixel_ratio=screen.devicePixelRatio(),
            )
        )
    return out


class _NumberWidget(QWidget):
    def __init__(self, screen: QScreen, number: int) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self._number = number
        self._screen = screen
        g = screen.geometry()
        self.setGeometry(g)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        size = min(rect.width(), rect.height()) // 3
        bg_rect = QRect(0, 0, size, size)
        bg_rect.moveCenter(rect.center())
        p.setBrush(QColor(0, 0, 0, 180))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(bg_rect, 30, 30)
        font = QFont("Segoe UI", size // 2)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(255, 255, 255, 240))
        p.drawText(bg_rect, Qt.AlignCenter, str(self._number))


class MonitorOverlay:
    """Owns one _NumberWidget per screen; show()/hide() together."""

    def __init__(self) -> None:
        self._widgets: list[_NumberWidget] = []
        self._hide_timer = QTimer()
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show(self) -> None:
        self.hide()
        for i, screen in enumerate(QGuiApplication.screens()):
            w = _NumberWidget(screen, i + 1)
            w.show()
            self._widgets.append(w)
        self._hide_timer.start(3000)

    def hide(self) -> None:
        self._hide_timer.stop()
        for w in self._widgets:
            w.hide()
            w.deleteLater()
        self._widgets.clear()
