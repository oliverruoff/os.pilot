from __future__ import annotations

import threading
import ctypes
from ctypes import byref, c_int32, c_uint32, c_void_p, Structure

from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication


class GlobalShortcuts(QObject):
    def __init__(self, parent, open_chat, open_voice, stop, show_last_answer) -> None:
        super().__init__(parent)
        self.shortcuts: list[QShortcut] = []
        self.listener = None
        self.backend = "none"
        if self._start_carbon_hotkeys(open_chat, open_voice, stop, show_last_answer):
            self.backend = "carbon"
        elif self._start_global_hotkeys(open_chat, open_voice, stop, show_last_answer):
            self.backend = "pynput"
        else:
            self.backend = "qt"
            self._add("Meta+.", open_chat)
            self._add("Meta+,", open_voice)
            self._add("Meta+<", stop)
            self._add("Meta+B", show_last_answer)

    def _start_carbon_hotkeys(self, open_chat, open_voice, stop, show_last_answer) -> bool:
        try:
            carbon = ctypes.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")
        except OSError:
            return False

        carbon.GetApplicationEventTarget.restype = c_void_p
        carbon.InstallEventHandler.argtypes = [c_void_p, c_void_p, c_uint32, c_void_p, c_void_p, c_void_p]
        carbon.InstallEventHandler.restype = c_int32
        carbon.GetEventParameter.argtypes = [c_void_p, c_uint32, c_uint32, c_void_p, c_uint32, c_void_p, c_void_p]
        carbon.GetEventParameter.restype = c_int32

        def fourcc(value: str) -> int:
            return int.from_bytes(value.encode("ascii"), "big")

        class EventTypeSpec(Structure):
            _fields_ = [("eventClass", c_uint32), ("eventKind", c_uint32)]

        class EventHotKeyID(Structure):
            _fields_ = [("signature", c_uint32), ("id", c_uint32)]

        carbon.RegisterEventHotKey.argtypes = [c_uint32, c_uint32, EventHotKeyID, c_void_p, c_uint32, c_void_p]
        carbon.RegisterEventHotKey.restype = c_int32

        callbacks = {1: open_voice, 2: open_chat, 3: stop, 4: stop, 5: show_last_answer}
        handler_type = ctypes.CFUNCTYPE(c_int32, c_void_p, c_void_p, c_void_p)

        def handler(_next_handler, event, _user_data):
            hotkey_id = EventHotKeyID()
            carbon.GetEventParameter(event, fourcc("----"), fourcc("hkid"), None, ctypes.sizeof(hotkey_id), None, byref(hotkey_id))
            callback = callbacks.get(hotkey_id.id)
            if callback:
                QTimer.singleShot(0, callback)
            return 0

        self._carbon_handler = handler_type(handler)
        target = carbon.GetApplicationEventTarget()
        event_type = EventTypeSpec(fourcc("keyb"), 5)
        if carbon.InstallEventHandler(target, self._carbon_handler, 1, byref(event_type), None, None) != 0:
            return False

        cmd_key = 1 << 8
        registrations = [
            (43, cmd_key, 1),  # Cmd + ,
            (47, cmd_key, 2),  # Cmd + .
            (10, cmd_key, 3),  # Cmd + < on ISO keyboards
            (50, cmd_key, 4),  # Cmd + < fallback key code
            (11, cmd_key, 5),  # Cmd + B
        ]
        self._carbon_refs = []
        for key_code, modifiers, hotkey_id in registrations:
            ref = c_void_p()
            status = carbon.RegisterEventHotKey(key_code, modifiers, EventHotKeyID(fourcc("OSPL"), hotkey_id), target, 0, byref(ref))
            if status == 0:
                self._carbon_refs.append(ref)
        return len(self._carbon_refs) >= 4

    def _start_global_hotkeys(self, open_chat, open_voice, stop, show_last_answer) -> bool:
        try:
            from pynput import keyboard
        except Exception:
            return False

        def dispatch(callback) -> None:
            QTimer.singleShot(0, callback)

        try:
            self.listener = keyboard.GlobalHotKeys(
                {
                    "<cmd>+.": lambda: dispatch(open_chat),
                    "<cmd>+,": lambda: dispatch(open_voice),
                    "<cmd>+<": lambda: dispatch(stop),
                    "<cmd>+b": lambda: dispatch(show_last_answer),
                }
            )
            threading.Thread(target=self.listener.run, daemon=True).start()
            return True
        except Exception:
            self.listener = None
            return False

    def _add(self, sequence: str, callback) -> None:
        shortcut = QShortcut(QKeySequence(sequence), QApplication.activeWindow() or self.parent())
        shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        shortcut.activated.connect(callback)
        self.shortcuts.append(shortcut)
