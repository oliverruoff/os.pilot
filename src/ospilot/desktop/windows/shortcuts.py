from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication


HOTKEYS = {
    "<alt_gr>+.": "open_chat",
    "<alt_gr>+,": "open_voice",
    "<alt_gr>+<": "stop",
    "<alt_gr>+b": "show_last_answer",
    "<ctrl>+<alt>+.": "open_chat",
    "<ctrl>+<alt>+,": "open_voice",
    "<ctrl>+<alt>+<": "stop",
    "<ctrl>+<alt>+b": "show_last_answer",
}


class GlobalShortcuts(QObject):
    triggered = Signal(str)

    def __init__(self, parent, open_chat, open_voice, stop, show_last_answer) -> None:
        super().__init__(parent)
        self.shortcuts: list[QShortcut] = []
        self.listener = None
        self.backend = "none"
        callbacks = {
            "open_chat": open_chat,
            "open_voice": open_voice,
            "stop": stop,
            "show_last_answer": show_last_answer,
        }
        self.triggered.connect(lambda name: callbacks[name]())
        if self._start_global_hotkeys():
            self.backend = "pynput"
        else:
            self.backend = "qt"
            self._add("AltGr+.", open_chat, parent)
            self._add("AltGr+,", open_voice, parent)
            self._add("AltGr+<", stop, parent)
            self._add("AltGr+B", show_last_answer, parent)
            self._add("Ctrl+Alt+.", open_chat, parent)
            self._add("Ctrl+Alt+,", open_voice, parent)
            self._add("Ctrl+Alt+<", stop, parent)
            self._add("Ctrl+Alt+B", show_last_answer, parent)

    def _start_global_hotkeys(self) -> bool:
        try:
            from pynput import keyboard
        except Exception:
            return False

        try:
            self.listener = keyboard.GlobalHotKeys(
                {
                    key: lambda name=name: self.triggered.emit(name)
                    for key, name in HOTKEYS.items()
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
