from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon


def _tray_icon() -> QIcon:
    custom = Path.home() / "Library" / "Application Support" / "OSPilot" / "ospilot_favicon.jpg"
    if custom.exists():
        return QIcon(str(custom))
    return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)


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
