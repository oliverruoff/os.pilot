from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from ospilot.core.config import AppConfig
from ospilot.desktop.backend import DesktopBackend


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
    desktop: DesktopBackend,
    show_message: Callable[[str], None] | None = None,
    tool_state: Callable[[str, str], None] | None = None,
    screenshot_visibility: Callable[[bool], None] | None = None,
    before_desktop_input: Callable[[], None] | None = None,
) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register("ospilot_get_active_context", lambda payload: desktop.get_active_context())
    registry.register("ospilot_capture_screenshot_current_mouse_monitor", lambda payload: _without_overlay(screenshot_visibility, lambda: desktop.capture_screenshot_current_mouse_monitor(config)))
    registry.register("ospilot_get_frontmost_ui_elements", lambda payload: desktop.get_frontmost_ui_elements(str(payload.get("query", "")), int(payload.get("limit", 120))))
    registry.register("ospilot_show_companion_message", lambda payload: _show_message(show_message, str(payload.get("text", ""))))
    registry.register("ospilot_move_mouse", lambda payload: _with_tool_state(tool_state, "ospilot_move_mouse", lambda: desktop.move_mouse(payload.get("target", {}), payload.get("duration_ms"))))
    registry.register("ospilot_press_hotkey", lambda payload: _desktop_input(screenshot_visibility, before_desktop_input, lambda: desktop.press_hotkey(list(payload.get("keys", [])))))
    registry.register("ospilot_read_clipboard", lambda payload: desktop.read_clipboard())
    registry.register("ospilot_write_clipboard", lambda payload: desktop.write_clipboard(str(payload.get("text", ""))))
    registry.register("ospilot_click", lambda payload: _desktop_input(screenshot_visibility, before_desktop_input, lambda: desktop.click(payload.get("target"), False)))
    registry.register("ospilot_right_click", lambda payload: _desktop_input(screenshot_visibility, before_desktop_input, lambda: desktop.right_click(payload.get("target"))))
    registry.register("ospilot_double_click", lambda payload: _desktop_input(screenshot_visibility, before_desktop_input, lambda: desktop.click(payload.get("target"), True)))
    registry.register("ospilot_type_text", lambda payload: _desktop_input(screenshot_visibility, before_desktop_input, lambda: desktop.type_text(str(payload.get("text", "")))))
    registry.register("ospilot_open_app", lambda payload: desktop.open_app(str(payload.get("app_name", ""))))
    return registry


def _without_overlay(screenshot_visibility: Callable[[bool], None] | None, action: Callable[[], dict[str, Any]], restore: bool = True) -> dict[str, Any]:
    if screenshot_visibility:
        screenshot_visibility(False)
        # Give the OS one frame to remove OSPilot's overlay before the desktop action,
        # so screenshots and clicks do not hit/respond to OSPilot's own bubble.
        time.sleep(0.15)
    try:
        return action()
    finally:
        if screenshot_visibility and restore:
            screenshot_visibility(True)


def _desktop_input(screenshot_visibility: Callable[[bool], None] | None, before_desktop_input: Callable[[], None] | None, action: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    if screenshot_visibility:
        screenshot_visibility(False)
        time.sleep(0.15)
    if before_desktop_input:
        before_desktop_input()
        time.sleep(0.15)
    return action()


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
