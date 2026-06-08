from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget

from ospilot.desktop.window import allow_fullscreen_overlay


class CursorHalo(QWidget):
    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.phase = 0.0
        self.mode = "moving"
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._follow_cursor)
        self.resize(88, 88)
        allow_fullscreen_overlay(self)

    def show_halo(self, mode: str = "moving") -> None:
        self.mode = mode
        allow_fullscreen_overlay(self)
        self._follow_cursor()
        self.show()
        allow_fullscreen_overlay(self)
        self.timer.start(16)

    def hide_halo(self) -> None:
        self.timer.stop()
        self.hide()

    def _follow_cursor(self) -> None:
        self.phase += 0.08
        pos = QCursor.pos()
        self.move(pos.x() - self.width() // 2, pos.y() - self.height() // 2)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        center = QPointF(self.width() / 2, self.height() / 2)
        pulse = 0.5 + 0.5 * math.sin(self.phase)
        colors = [QColor(123, 165, 214, 72), QColor(105, 126, 158, 54), QColor(122, 171, 165, 38)]
        if self.mode == "error":
            colors = [QColor(205, 104, 119, 82), QColor(185, 131, 93, 54), QColor(145, 132, 183, 34)]
        for index, color in enumerate(colors):
            radius = 22 + index * 12 + pulse * 8
            offset = QPointF(math.cos(self.phase + index * 2.1) * 5, math.sin(self.phase + index * 2.1) * 5)
            gradient = QRadialGradient(center + offset, radius)
            gradient.setColorAt(0.0, color)
            gradient.setColorAt(0.55, QColor(color.red(), color.green(), color.blue(), max(18, color.alpha() // 3)))
            gradient.setColorAt(1.0, QColor(color.red(), color.green(), color.blue(), 0))
            painter.setBrush(gradient)
            painter.drawEllipse(center + offset, radius, radius)
