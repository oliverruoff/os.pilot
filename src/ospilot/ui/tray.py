from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def _emoji_tray_icon() -> QIcon:
    size = 64
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    font = QFont("Apple Color Emoji")
    font.setPixelSize(44)
    painter.setFont(font)
    painter.drawText(QRect(0, 4, size, size), Qt.AlignmentFlag.AlignCenter, "🧑🏻‍✈️")
    painter.end()

    # Convert the emoji to a monochrome template-style icon. macOS can tint mask icons
    # for light/dark menu bars; other platforms get a crisp black silhouette.
    for y in range(size):
        for x in range(size):
            alpha = QColor(image.pixelColor(x, y)).alpha()
            if alpha:
                image.setPixelColor(x, y, QColor(0, 0, 0, alpha))

    icon = QIcon(QPixmap.fromImage(image))
    icon.setIsMask(True)
    return icon


def _tray_icon() -> QIcon:
    return _emoji_tray_icon()


class TrayController:
    def __init__(self, open_chat, open_voice, new_session, stop, quit_app) -> None:
        self.tray = QSystemTrayIcon(_tray_icon())
        menu = QMenu()
        for label, callback in (
            ("Open Chat", open_chat),
            ("Open Voice", open_voice),
            ("New Session", new_session),
            ("Stop", stop),
            ("Quit", quit_app),
        ):
            action = QAction(label, menu)
            action.triggered.connect(callback)
            menu.addAction(action)
        self.tray.setContextMenu(menu)
        self.tray.setToolTip("OSPilot")

    def show(self) -> None:
        self.tray.show()

    def notify(self, title: str, message: str) -> None:
        self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 2000)
