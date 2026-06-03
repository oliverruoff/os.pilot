from __future__ import annotations

import math
import threading
import time
from typing import Any, Callable

from .coordinates import Bounds, ease_in_out_cubic, normalize_target


StopPredicate = Callable[[], bool]


class MouseController:
    def __init__(self) -> None:
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def reset(self) -> None:
        self._stop.clear()

    def move_mouse(self, target: dict[str, Any], duration_ms: int | None = None) -> dict:
        import Quartz

        start_event = Quartz.CGEventCreate(None)
        start_pos = Quartz.CGEventGetLocation(start_event)
        display_id, display_bounds = _display_for_point(Quartz, start_pos.x, start_pos.y)
        if display_id is None or display_bounds is None:
            return {"ok": False, "tool": "ospilot_move_mouse", "error": "no screen found"}
        bounds = Bounds(display_bounds.origin.x, display_bounds.origin.y, display_bounds.size.width, display_bounds.size.height)
        end_x, end_y = normalize_target(target, bounds)
        distance = math.dist((start_pos.x, start_pos.y), (end_x, end_y))
        duration = max(0.05, (duration_ms if duration_ms is not None else min(800, max(300, distance * 0.8))) / 1000)
        steps = max(8, int(duration * 60))
        self.reset()
        for index in range(steps + 1):
            if self._stop.is_set():
                return {"ok": False, "tool": "ospilot_move_mouse", "error": "stopped"}
            t = ease_in_out_cubic(index / steps)
            Quartz.CGWarpMouseCursorPosition((start_pos.x + (end_x - start_pos.x) * t, start_pos.y + (end_y - start_pos.y) * t))
            time.sleep(duration / steps)
        return {"ok": True, "tool": "ospilot_move_mouse", "target": {"x": end_x, "y": end_y}, "metadata": {"duration_ms": round(duration * 1000)}}

    def click(self, target: dict[str, Any] | None = None, double: bool = False) -> dict:
        if target:
            moved = self.move_mouse(target, 250)
            if not moved.get("ok"):
                return moved
        try:
            import Quartz

            pos = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
            event_type_down = Quartz.kCGEventLeftMouseDown
            event_type_up = Quartz.kCGEventLeftMouseUp
            for _ in range(2 if double else 1):
                down = Quartz.CGEventCreateMouseEvent(None, event_type_down, (pos.x, pos.y), Quartz.kCGMouseButtonLeft)
                up = Quartz.CGEventCreateMouseEvent(None, event_type_up, (pos.x, pos.y), Quartz.kCGMouseButtonLeft)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)
            return {"ok": True, "tool": "ospilot_double_click" if double else "ospilot_click"}
        except Exception as exc:
            return {"ok": False, "tool": "ospilot_double_click" if double else "ospilot_click", "error": str(exc)}


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
