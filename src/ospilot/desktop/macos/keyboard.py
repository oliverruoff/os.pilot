from __future__ import annotations

import subprocess


KEY_ALIASES = {"cmd": "command", "command": "command", "ctrl": "control", "control": "control", "alt": "option", "option": "option", "shift": "shift"}


def _applescript_string(value: str) -> str:
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def press_hotkey(keys: list[str]) -> dict:
    if not keys:
        return {"ok": False, "tool": "ospilot_press_hotkey", "error": "keys must not be empty"}
    modifiers = [KEY_ALIASES[k.lower()] for k in keys[:-1] if k.lower() in KEY_ALIASES]
    key = keys[-1]
    using = " using " + " down, ".join(modifiers) + " down" if modifiers else ""
    script = f'tell application "System Events" to keystroke {_applescript_string(key)}{using}'
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)
    return {"ok": result.returncode == 0, "tool": "ospilot_press_hotkey", "stderr": result.stderr, "metadata": {"exit_code": result.returncode}}


def type_text(text: str) -> dict:
    script = f'tell application "System Events" to keystroke {_applescript_string(text)}'
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=20)
    return {"ok": result.returncode == 0, "tool": "ospilot_type_text", "stderr": result.stderr, "metadata": {"exit_code": result.returncode}}
