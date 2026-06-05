from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication


class GlobalShortcuts:
    backend = "qt"

    def __init__(self, parent, open_chat, open_voice, stop) -> None:
        self.shortcuts: list[QShortcut] = []
        self._add("Ctrl+.", open_chat, parent)
        self._add("Ctrl+,", open_voice, parent)
        self._add("Ctrl+<", stop, parent)

    def _add(self, sequence: str, callback, parent) -> None:
        shortcut = QShortcut(QKeySequence(sequence), QApplication.activeWindow() or parent)
        shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        shortcut.activated.connect(callback)
        self.shortcuts.append(shortcut)
