from __future__ import annotations

import math
import os
import threading
import time
from typing import Any, Callable

from ospilot.desktop.common.coordinates import Bounds, clamp_point, human_mouse_path, normalize_target
from .screenshot import get_last_screenshot_context


StopPredicate = Callable[[], bool]
MOUSE_SPEED_SCALE = 3.0  # 1/3 speed: triple the movement duration.
MIN_MOVE_DURATION_MS = 60
MAX_MOVE_DURATION_MS = 700
MAX_SLOWED_MOVE_DURATION_MS = int(MAX_MOVE_DURATION_MS * MOUSE_SPEED_SCALE)


class MouseController:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def stop(self) -> None:
        self._stop.set()

    def reset(self) -> None:
        self._stop.clear()

    def move_mouse(self, target: dict[str, Any], duration_ms: int | None = None) -> dict:
        import Quartz

        with self._lock:
            start_event = Quartz.CGEventCreate(None)
            start_pos = Quartz.CGEventGetLocation(start_event)
            display_id, display_bounds = _display_for_point(Quartz, start_pos.x, start_pos.y)
            if display_id is None or display_bounds is None:
                return {"ok": False, "tool": "ospilot_move_mouse", "error": "no screen found"}
            start_bounds = Bounds(display_bounds.origin.x, display_bounds.origin.y, display_bounds.size.width, display_bounds.size.height)
            screenshot_context = get_last_screenshot_context()
            end_x, end_y = normalize_target(target, start_bounds, screenshot_context)
            target_bounds = _bounds_for_target(Quartz, end_x, end_y, target, start_bounds, screenshot_context)
            end_x, end_y = clamp_point(end_x, end_y, target_bounds)
            distance = math.dist((start_pos.x, start_pos.y), (end_x, end_y))
            requested_ms = duration_ms if isinstance(duration_ms, int | float) else None
            auto_ms = min(350, max(80, 45 + distance * 0.24))
            base_duration_ms = requested_ms if requested_ms is not None else auto_ms
            duration_ms_final = min(MAX_SLOWED_MOVE_DURATION_MS, max(MIN_MOVE_DURATION_MS, base_duration_ms) * MOUSE_SPEED_SCALE)
            duration = duration_ms_final / 1000
            steps = max(10, min(240, int(duration * 120)))
            path = human_mouse_path((start_pos.x, start_pos.y), (end_x, end_y), steps)
            self.reset()
            last = time.perf_counter()
            for index, point in enumerate(path):
                if self._stop.is_set():
                    return {"ok": False, "tool": "ospilot_move_mouse", "error": "stopped"}
                _move_cursor_to_point(Quartz, point[0], point[1])
                if index < len(path) - 1:
                    # Tiny cadence variation avoids a perfectly mechanical 60Hz line.
                    slice_duration = duration / steps * (0.72 + 0.56 * ((index % 5) / 4))
                    last += slice_duration
                    time.sleep(max(0.0, last - time.perf_counter()))
            final_x, final_y, final_error_px, settle_attempts = _settle_cursor_at_point(Quartz, end_x, end_y)
            return {"ok": True, "tool": "ospilot_move_mouse", "target": {"x": end_x, "y": end_y}, "actual": {"x": final_x, "y": final_y}, "metadata": {"duration_ms": round(duration * 1000), "steps": steps, "profile": "human_bezier", "final_error_px": round(final_error_px, 2), "settle_attempts": settle_attempts}}

    def click(self, target: dict[str, Any] | None = None, double: bool = False) -> dict:
        return self._click(target, button="left", double=double)

    def right_click(self, target: dict[str, Any] | None = None) -> dict:
        return self._click(target, button="right", double=False)

    def _click(self, target: dict[str, Any] | None = None, button: str = "left", double: bool = False) -> dict:
        tool = _click_tool(button, double)
        click_target: dict[str, float] | None = None
        if target:
            moved = self.move_mouse(target, 90)
            if not moved.get("ok"):
                return moved
            moved_target = moved.get("target")
            if isinstance(moved_target, dict) and isinstance(moved_target.get("x"), int | float) and isinstance(moved_target.get("y"), int | float):
                click_target = {"x": float(moved_target["x"]), "y": float(moved_target["y"])}
            time.sleep(0.06)
        try:
            import Quartz

            source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
            if click_target:
                pos_x = click_target["x"]
                pos_y = click_target["y"]
                actual_x, actual_y, final_error_px, settle_attempts = _settle_cursor_at_point(Quartz, pos_x, pos_y)
            else:
                pos = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
                pos_x = float(pos.x)
                pos_y = float(pos.y)
                actual_x = pos_x
                actual_y = pos_y
                final_error_px = 0.0
                settle_attempts = 0
            _activate_app_at_point(Quartz, pos_x, pos_y)
            event_type_down, event_type_up, quartz_button = _quartz_button_events(Quartz, button)
            for index in range(2 if double else 1):
                click_state = index + 1 if double else 1
                down = Quartz.CGEventCreateMouseEvent(source, event_type_down, (pos_x, pos_y), quartz_button)
                up = Quartz.CGEventCreateMouseEvent(source, event_type_up, (pos_x, pos_y), quartz_button)
                Quartz.CGEventSetIntegerValueField(down, Quartz.kCGMouseEventClickState, click_state)
                Quartz.CGEventSetIntegerValueField(up, Quartz.kCGMouseEventClickState, click_state)
                _post_mouse_event(Quartz, down)
                time.sleep(0.045)
                _post_mouse_event(Quartz, up)
                if double and index == 0:
                    time.sleep(0.06)
            return {"ok": True, "tool": tool, "target": {"x": pos_x, "y": pos_y}, "actual": {"x": actual_x, "y": actual_y}, "metadata": {"event_tap": "hid", "button": button, "final_error_px": round(final_error_px, 2), "settle_attempts": settle_attempts}}
        except Exception as exc:
            return {"ok": False, "tool": tool, "error": str(exc)}


def _display_for_point(Quartz, x: float, y: float):
    err, displays, count = Quartz.CGGetActiveDisplayList(32, None, None)
    if err != 0:
        return None, None
    for display_id in displays[:count]:
        bounds = Quartz.CGDisplayBounds(display_id)
        if bounds.origin.x <= x <= bounds.origin.x + bounds.size.width and bounds.origin.y <= y <= bounds.origin.y + bounds.size.height:
            return display_id, bounds
    if count:
        display_id = displays[0]
        return display_id, Quartz.CGDisplayBounds(display_id)
    return None, None


def _bounds_for_target(Quartz, x: float, y: float, target: dict[str, Any], fallback: Bounds, screenshot_context: dict[str, Any] | None) -> Bounds:
    coordinate_space = str(target.get("coordinate_space", "")).strip()
    if coordinate_space == "screenshot_pixel":
        screenshot_bounds = _bounds_from_screenshot_context(screenshot_context)
        if screenshot_bounds is not None:
            return screenshot_bounds

    display_id, display_bounds = _display_for_point(Quartz, x, y)
    if display_id is not None and display_bounds is not None:
        return Bounds(display_bounds.origin.x, display_bounds.origin.y, display_bounds.size.width, display_bounds.size.height)
    return fallback


def _bounds_from_screenshot_context(screenshot_context: dict[str, Any] | None) -> Bounds | None:
    if not screenshot_context:
        return None
    monitor_bounds = screenshot_context.get("monitor_bounds")
    if not isinstance(monitor_bounds, dict):
        return None
    x = monitor_bounds.get("x")
    y = monitor_bounds.get("y")
    width = monitor_bounds.get("width")
    height = monitor_bounds.get("height")
    if not all(isinstance(value, int | float) for value in (x, y, width, height)):
        return None
    if width <= 0 or height <= 0:
        return None
    return Bounds(float(x), float(y), float(width), float(height))


def _move_cursor_to_point(Quartz, x: float, y: float) -> None:
    display_id, display_bounds = _display_for_point(Quartz, x, y)
    if display_id is not None and display_bounds is not None:
        try:
            err = Quartz.CGDisplayMoveCursorToPoint(display_id, (x - display_bounds.origin.x, y - display_bounds.origin.y))
            if err == 0:
                return
        except Exception:
            pass
    Quartz.CGWarpMouseCursorPosition((x, y))


def _settle_cursor_at_point(Quartz, x: float, y: float) -> tuple[float, float, float, int]:
    final_x = x
    final_y = y
    final_error_px = float("inf")
    for attempt in range(1, 6):
        _move_cursor_to_point(Quartz, x, y)
        time.sleep(0.01)
        pos = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
        final_x = float(pos.x)
        final_y = float(pos.y)
        final_error_px = math.dist((final_x, final_y), (x, y))
        if final_error_px <= 0.25:
            return final_x, final_y, final_error_px, attempt
    return final_x, final_y, final_error_px, 5


def _click_tool(button: str, double: bool) -> str:
    if button == "right":
        return "ospilot_right_click"
    return "ospilot_double_click" if double else "ospilot_click"


def _quartz_button_events(Quartz, button: str):
    if button == "right":
        return Quartz.kCGEventRightMouseDown, Quartz.kCGEventRightMouseUp, Quartz.kCGMouseButtonRight
    return Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp, Quartz.kCGMouseButtonLeft


def _post_mouse_event(Quartz, event) -> None:
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def _activate_app_at_point(Quartz, x: float, y: float) -> None:
    pid = _pid_at_point(Quartz, x, y)
    if pid is None or pid == os.getpid():
        return
    try:
        from AppKit import NSApplicationActivateIgnoringOtherApps, NSRunningApplication

        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        if app is not None:
            app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
            time.sleep(0.12)
    except Exception:
        return


def _pid_at_point(Quartz, x: float, y: float) -> int | None:
    try:
        windows = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID) or []
    except Exception:
        return None

    for window in windows:
        try:
            if int(window.get("kCGWindowLayer", 0)) != 0:
                continue
            pid = int(window.get("kCGWindowOwnerPID", 0))
            if not pid or pid == os.getpid():
                continue
            bounds = window.get("kCGWindowBounds") or {}
            wx = float(bounds.get("X", 0))
            wy = float(bounds.get("Y", 0))
            ww = float(bounds.get("Width", 0))
            wh = float(bounds.get("Height", 0))
            if wx <= x <= wx + ww and wy <= y <= wy + wh:
                return pid
        except Exception:
            continue
    return None
