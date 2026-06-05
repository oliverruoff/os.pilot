from __future__ import annotations

import platform
from typing import Any

from ospilot.core.config import AppConfig
from ospilot.desktop.common.clipboard import read_clipboard, write_clipboard

from .shortcuts import GlobalShortcuts


def _not_implemented(tool: str) -> dict[str, Any]:
    return {"ok": False, "tool": tool, "platform": "windows", "error": "not implemented on windows yet"}


class WindowsDesktopBackend:
    name = "windows"

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def stop(self) -> None:
        return

    def configure_background_app(self) -> None:
        return

    def create_global_shortcuts(self, parent: Any, open_chat: Any, open_voice: Any, stop: Any) -> GlobalShortcuts:
        return GlobalShortcuts(parent, open_chat, open_voice, stop)

    def get_active_context(self) -> dict[str, Any]:
        return {"ok": True, "tool": "ospilot_get_active_context", "platform": platform.platform(), "mouse_position": None}

    def capture_screenshot_current_mouse_monitor(self, config: AppConfig) -> dict[str, Any]:
        return _not_implemented("ospilot_capture_screenshot_current_mouse_monitor")

    def get_frontmost_ui_elements(self, query: str = "", limit: int = 120) -> dict[str, Any]:
        return _not_implemented("ospilot_get_frontmost_ui_elements")

    def move_mouse(self, target: dict[str, Any], duration_ms: int | None = None) -> dict[str, Any]:
        return _not_implemented("ospilot_move_mouse")

    def click(self, target: dict[str, Any] | None = None, double: bool = False) -> dict[str, Any]:
        return _not_implemented("ospilot_double_click" if double else "ospilot_click")

    def right_click(self, target: dict[str, Any] | None = None) -> dict[str, Any]:
        return _not_implemented("ospilot_right_click")

    def press_hotkey(self, keys: list[str]) -> dict[str, Any]:
        return _not_implemented("ospilot_press_hotkey")

    def type_text(self, text: str) -> dict[str, Any]:
        return _not_implemented("ospilot_type_text")

    def focus_app(self, pid: int) -> dict[str, Any]:
        return _not_implemented("ospilot_focus_app")

    def open_app(self, app_name: str) -> dict[str, Any]:
        return _not_implemented("ospilot_open_app")

    def read_clipboard(self) -> dict[str, Any]:
        return read_clipboard()

    def write_clipboard(self, text: str) -> dict[str, Any]:
        return write_clipboard(text)
