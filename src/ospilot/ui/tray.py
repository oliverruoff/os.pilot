from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from ospilot.pi.runtime import PiSession


def _pilot_terminal_icon() -> QIcon:
    size = 64
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 255))

    body = QRectF(10, 14, 44, 36)
    painter.drawRoundedRect(body, 13, 13)

    notch = QPainterPath()
    notch.moveTo(23, 14)
    notch.lineTo(29, 7)
    notch.lineTo(35, 14)
    notch.closeSubpath()
    painter.drawPath(notch)

    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
    painter.drawRoundedRect(QRectF(15, 20, 34, 21), 6, 6)

    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    painter.setPen(QPen(QColor(0, 0, 0, 255), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.drawLine(QPointF(21, 30), QPointF(27, 35))
    painter.drawLine(QPointF(27, 25), QPointF(21, 30))
    painter.drawLine(QPointF(33, 35), QPointF(42, 35))

    font = QFont("Menlo")
    font.setPixelSize(9)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(QRect(0, 46, size, 12), Qt.AlignmentFlag.AlignCenter, "PI")
    painter.end()

    icon = QIcon(QPixmap.fromImage(image))
    icon.setIsMask(True)
    return icon


def _tray_icon() -> QIcon:
    return _pilot_terminal_icon()


class TrayController:
    def __init__(
        self,
        open_chat,
        open_voice,
        new_session,
        list_sessions: Callable[[], Sequence[PiSession]],
        switch_session: Callable[[PiSession], None],
        stop,
        quit_app,
    ) -> None:
        self._list_sessions = list_sessions
        self._switch_session = switch_session
        self.tray = QSystemTrayIcon(_tray_icon())
        menu = QMenu()
        self._add_action(menu, "Open Chat", open_chat)
        self._add_action(menu, "Open Voice", open_voice)
        self._add_action(menu, "New Session", new_session)
        self.sessions_menu = menu.addMenu("Sessions")
        self.sessions_menu.aboutToShow.connect(self._populate_sessions_menu)
        self._add_action(menu, "Stop", stop)
        self._add_action(menu, "Quit", quit_app)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("OSPilot")

    def _add_action(self, menu: QMenu, label: str, callback) -> QAction:
        action = QAction(label, menu)
        action.triggered.connect(callback)
        menu.addAction(action)
        return action

    def _populate_sessions_menu(self) -> None:
        self.sessions_menu.clear()
        sessions = list(self._list_sessions())
        if not sessions:
            action = QAction("No sessions found", self.sessions_menu)
            action.setEnabled(False)
            self.sessions_menu.addAction(action)
            return
        for session in sessions:
            action = QAction(session.title, self.sessions_menu)
            action.setToolTip(str(session.path))
            action.triggered.connect(lambda _checked=False, selected=session: self._switch_session(selected))
            self.sessions_menu.addAction(action)

    def show(self) -> None:
        self.tray.show()

    def notify(self, title: str, message: str) -> None:
        self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 2000)
