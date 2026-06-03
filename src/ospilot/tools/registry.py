from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ospilot.config import AppConfig

from .apps import open_app
from .clipboard import read_clipboard, write_clipboard
from .context import get_active_context
from .keyboard import press_hotkey, type_text
from .mouse import MouseController
from .screenshot import capture_screenshot_current_mouse_monitor
from .shell import run_shell_command


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


class ToolRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, name: str, handler: ToolHandler) -> None:
        self._handlers[name] = handler

    def call(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        handler = self._handlers.get(name)
        if not handler:
            return {"ok": False, "tool": name, "error": "unknown tool"}
        try:
            return handler(payload)
        except Exception as exc:
            return {"ok": False, "tool": name, "error": str(exc)}


def build_default_registry(
    config: AppConfig,
    mouse: MouseController | None = None,
    show_message: Callable[[str], None] | None = None,
    tool_state: Callable[[str, str], None] | None = None,
) -> ToolRegistry:
    registry = ToolRegistry()
    mouse = mouse or MouseController()
    registry.register("ospilot_get_active_context", lambda payload: get_active_context())
    registry.register("ospilot_capture_screenshot_current_mouse_monitor", lambda payload: capture_screenshot_current_mouse_monitor(config))
    registry.register("ospilot_show_companion_message", lambda payload: _show_message(show_message, str(payload.get("text", ""))))
    registry.register("ospilot_move_mouse", lambda payload: _with_tool_state(tool_state, "ospilot_move_mouse", lambda: mouse.move_mouse(payload.get("target", {}), payload.get("duration_ms"))))
    registry.register("ospilot_press_hotkey", lambda payload: press_hotkey(list(payload.get("keys", []))))
    registry.register("ospilot_read_clipboard", lambda payload: read_clipboard())
    registry.register("ospilot_write_clipboard", lambda payload: write_clipboard(str(payload.get("text", ""))))
    registry.register("ospilot_run_shell_command", lambda payload: run_shell_command(str(payload.get("command", "")), payload.get("cwd")))
    registry.register("ospilot_click", lambda payload: mouse.click(payload.get("target"), False))
    registry.register("ospilot_double_click", lambda payload: mouse.click(payload.get("target"), True))
    registry.register("ospilot_type_text", lambda payload: type_text(str(payload.get("text", ""))))
    registry.register("ospilot_open_app", lambda payload: open_app(str(payload.get("app_name", ""))))
    return registry


def _show_message(callback: Callable[[str], None] | None, text: str) -> dict[str, Any]:
    if callback:
        callback(text)
    return {"ok": True, "tool": "ospilot_show_companion_message"}


def _with_tool_state(callback: Callable[[str, str], None] | None, name: str, action: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    if callback:
        callback(name, "start")
    try:
        return action()
    finally:
        if callback:
            callback(name, "end")
