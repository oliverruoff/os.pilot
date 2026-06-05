from __future__ import annotations

import time


KEY_ALIASES = {
    "cmd": "cmd",
    "command": "cmd",
    "win": "cmd",
    "windows": "cmd",
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "option": "alt",
    "altgr": "alt_gr",
    "shift": "shift",
    "enter": "enter",
    "return": "enter",
    "escape": "esc",
    "esc": "esc",
    "tab": "tab",
    "space": "space",
    "backspace": "backspace",
    "delete": "delete",
}


def press_hotkey(keys: list[str]) -> dict:
    tool = "ospilot_press_hotkey"
    if not keys:
        return {"ok": False, "tool": tool, "error": "keys must not be empty"}
    try:
        from pynput.keyboard import Controller

        keyboard = Controller()
        normalized = [_normalize_key(key) for key in keys]
        pressed = [_pynput_key(key) for key in normalized]
        for key in pressed:
            keyboard.press(key)
            time.sleep(0.015)
        for key in reversed(pressed):
            keyboard.release(key)
        return {"ok": True, "tool": tool, "metadata": {"keys": normalized}}
    except Exception as exc:
        return {"ok": False, "tool": tool, "error": str(exc)}


def type_text(text: str) -> dict:
    tool = "ospilot_type_text"
    try:
        from pynput.keyboard import Controller

        Controller().type(text)
        return {"ok": True, "tool": tool, "metadata": {"length": len(text)}}
    except Exception as exc:
        return {"ok": False, "tool": tool, "error": str(exc)}


def _normalize_key(key: str) -> str:
    lowered = str(key).strip().lower()
    return KEY_ALIASES.get(lowered, lowered)


def _pynput_key(key: str):
    from pynput.keyboard import Key

    mapping = {
        "cmd": Key.cmd,
        "ctrl": Key.ctrl,
        "alt": Key.alt,
        "alt_gr": Key.alt_gr,
        "shift": Key.shift,
        "enter": Key.enter,
        "esc": Key.esc,
        "tab": Key.tab,
        "space": Key.space,
        "backspace": Key.backspace,
        "delete": Key.delete,
        "up": Key.up,
        "down": Key.down,
        "left": Key.left,
        "right": Key.right,
    }
    return mapping.get(key, key)
