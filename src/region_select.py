"""Full-screen drag-to-select rectangle across all monitors."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget


_BUTTON_STYLE_RECORD = """
QPushButton {
    background-color: #d12d2d;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font: bold 13px 'Segoe UI';
}
QPushButton:hover { background-color: #e74040; }
QPushButton:pressed { background-color: #b02323; }
"""

_BUTTON_STYLE_CANCEL = """
QPushButton {
    background-color: rgba(60,60,60,230);
    color: white;
    border: 1px solid rgba(255,255,255,80);
    border-radius: 6px;
    padding: 8px 18px;
    font: bold 13px 'Segoe UI';
}
QPushButton:hover { background-color: rgba(90,90,90,230); }
QPushButton:pressed { background-color: rgba(40,40,40,230); }
"""


class RegionSelector(QWidget):
    selected = Signal(QRect)  # emits the chosen rect in virtual desktop coords (logical pixels)
    cancelled = Signal()

    def __init__(self) -> None:
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setCursor(Qt.CrossCursor)
        vd = QRect()
        for s in QGuiApplication.screens():
            vd = vd.united(s.geometry())
        self._virtual_desktop = vd
        self.setGeometry(vd)
        self._origin: Optional[QPoint] = None
        self._current: Optional[QPoint] = None
        self._has_release = False  # mouse has been released → show action buttons
        self.setFocusPolicy(Qt.StrongFocus)

        # Action buttons (hidden until selection complete)
        self._toolbar = QWidget(self)
        bar = QHBoxLayout(self._toolbar)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(8)
        self._btn_record = QPushButton("● Record")
        self._btn_record.setStyleSheet(_BUTTON_STYLE_RECORD)
        self._btn_record.setCursor(Qt.PointingHandCursor)
        self._btn_record.clicked.connect(self._confirm)
        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.setStyleSheet(_BUTTON_STYLE_CANCEL)
        self._btn_cancel.setCursor(Qt.PointingHandCursor)
        self._btn_cancel.clicked.connect(self._cancel)
        bar.addWidget(self._btn_record)
        bar.addWidget(self._btn_cancel)
        self._toolbar.hide()
        self._toolbar.adjustSize()

    def _selection(self) -> QRect:
        if self._origin is None or self._current is None:
            return QRect()
        return QRect(self._origin, self._current).normalized()

    def _position_toolbar(self) -> None:
        sel = self._selection()
        if sel.width() < 8 or sel.height() < 8:
            self._toolbar.hide()
            return
        self._toolbar.adjustSize()
        tw = self._toolbar.width()
        th = self._toolbar.height()
        # Prefer below the selection, right-aligned; if it would go off-screen, place above.
        x = sel.x() + sel.width() - tw
        y = sel.y() + sel.height() + 8
        if y + th > self.height() - 4:
            y = sel.y() - th - 8
        if x < 4:
            x = 4
        if y < 4:
            y = sel.y() + 4  # fallback inside selection
        self._toolbar.move(x, y)
        self._toolbar.show()
        self._toolbar.raise_()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        full = self.rect()
        p.fillRect(full, QColor(0, 0, 0, 110))
        sel = self._selection()
        if sel.isValid() and not sel.isEmpty():
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            p.fillRect(sel, Qt.transparent)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            pen = QPen(QColor(255, 255, 255, 230))
            pen.setWidth(2)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(sel)
            # Live readout
            label = f"{sel.width()} x {sel.height()}  @  {sel.x()},{sel.y()}"
            font = QFont("Segoe UI", 12)
            font.setBold(True)
            p.setFont(font)
            metrics = p.fontMetrics()
            tw = metrics.horizontalAdvance(label) + 16
            th = metrics.height() + 6
            tx = sel.x()
            ty = sel.y() - th - 4
            if ty < 0:
                ty = sel.y() + sel.height() + 4
            p.fillRect(tx, ty, tw, th, QColor(0, 0, 0, 200))
            p.setPen(QColor(255, 255, 255))
            p.drawText(tx + 8, ty + metrics.ascent() + 3, label)

        # Persistent hint at top — visible at all times
        hint = ("Drag to select a region   •   click ● Record or press Enter to start"
                "   •   Esc to cancel")
        font = QFont("Segoe UI", 13)
        font.setBold(True)
        p.setFont(font)
        metrics = p.fontMetrics()
        tw = metrics.horizontalAdvance(hint) + 24
        th = metrics.height() + 14
        tx = (full.width() - tw) // 2
        ty = 20
        p.setBrush(QColor(0, 0, 0, 200))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(tx, ty, tw, th, 8, 8)
        p.setPen(QColor(255, 255, 255, 240))
        p.drawText(tx + 12, ty + metrics.ascent() + 6, hint)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._origin = event.position().toPoint()
            self._current = self._origin
            self._has_release = False
            self._toolbar.hide()
            self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._origin is not None and not self._has_release:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self._origin is not None:
            self._current = event.position().toPoint()
            self._has_release = True
            self.update()
            self._position_toolbar()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self._cancel()
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._confirm()

    def _confirm(self) -> None:
        sel = self._selection()
        if sel.width() < 8 or sel.height() < 8:
            self._cancel()
            return
        global_rect = QRect(
            sel.x() + self._virtual_desktop.x(),
            sel.y() + self._virtual_desktop.y(),
            sel.width(),
            sel.height(),
        )
        self.selected.emit(global_rect)
        self.close()

    def _cancel(self) -> None:
        self.cancelled.emit()
        self.close()
