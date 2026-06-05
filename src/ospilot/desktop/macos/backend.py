from __future__ import annotations

from typing import Any

from ospilot.core.config import AppConfig
from ospilot.desktop.common.clipboard import read_clipboard, write_clipboard

from .apps import open_app
from .context import get_active_context
from .keyboard import press_hotkey, type_text
from .mouse import MouseController
from .screenshot import capture_screenshot_current_mouse_monitor
from .shortcuts import GlobalShortcuts
from .ui_elements import get_frontmost_ui_elements
from .window import configure_background_app


class MacOSDesktopBackend:
    name = "macos"

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.mouse = MouseController()

    def stop(self) -> None:
        self.mouse.stop()

    def configure_background_app(self) -> None:
        configure_background_app()

    def create_global_shortcuts(self, parent: Any, open_chat: Any, open_voice: Any, stop: Any) -> GlobalShortcuts:
        return GlobalShortcuts(parent, open_chat, open_voice, stop)

    def get_active_context(self) -> dict[str, Any]:
        return get_active_context()

    def capture_screenshot_current_mouse_monitor(self, config: AppConfig) -> dict[str, Any]:
        return capture_screenshot_current_mouse_monitor(config)

    def get_frontmost_ui_elements(self, query: str = "", limit: int = 120) -> dict[str, Any]:
        return get_frontmost_ui_elements(query, limit)

    def move_mouse(self, target: dict[str, Any], duration_ms: int | None = None) -> dict[str, Any]:
        return self.mouse.move_mouse(target, duration_ms)

    def click(self, target: dict[str, Any] | None = None, double: bool = False) -> dict[str, Any]:
        return self.mouse.click(target, double)

    def right_click(self, target: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.mouse.right_click(target)

    def press_hotkey(self, keys: list[str]) -> dict[str, Any]:
        return press_hotkey(keys)

    def type_text(self, text: str) -> dict[str, Any]:
        return type_text(text)

    def open_app(self, app_name: str) -> dict[str, Any]:
        return open_app(app_name)

    def read_clipboard(self) -> dict[str, Any]:
        return read_clipboard()

    def write_clipboard(self, text: str) -> dict[str, Any]:
        return write_clipboard(text)
