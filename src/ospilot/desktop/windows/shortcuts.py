from __future__ import annotations

import threading

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication


class GlobalShortcuts:
    def __init__(self, parent, open_chat, open_voice, stop) -> None:
        self.shortcuts: list[QShortcut] = []
        self.listener = None
        self.backend = "none"
        if self._start_global_hotkeys(open_chat, open_voice, stop):
            self.backend = "pynput"
        else:
            self.backend = "qt"
            self._add("Ctrl+Alt+.", open_chat, parent)
            self._add("Ctrl+Alt+,", open_voice, parent)
            self._add("Ctrl+Alt+<", stop, parent)

    def _start_global_hotkeys(self, open_chat, open_voice, stop) -> bool:
        try:
            from pynput import keyboard
        except Exception:
            return False

        def dispatch(callback) -> None:
            QTimer.singleShot(0, callback)

        try:
            self.listener = keyboard.GlobalHotKeys(
                {
                    "<ctrl>+<alt>+.": lambda: dispatch(open_chat),
                    "<ctrl>+<alt>+,": lambda: dispatch(open_voice),
                    "<ctrl>+<alt>+<": lambda: dispatch(stop),
                }
            )
            threading.Thread(target=self.listener.run, daemon=True).start()
            return True
        except Exception:
            self.listener = None
            return False

    def _add(self, sequence: str, callback, parent) -> None:
        shortcut = QShortcut(QKeySequence(sequence), QApplication.activeWindow() or parent)
        shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        shortcut.activated.connect(callback)
        self.shortcuts.append(shortcut)
