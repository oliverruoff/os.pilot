from __future__ import annotations

import math
import threading
import time
from typing import Any, Callable

from ospilot.desktop.common.coordinates import Bounds, clamp_point, human_mouse_path, normalize_target
from .screenshot import get_last_screenshot_context


StopPredicate = Callable[[], bool]


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
            bounds = Bounds(display_bounds.origin.x, display_bounds.origin.y, display_bounds.size.width, display_bounds.size.height)
            end_x, end_y = normalize_target(target, bounds, get_last_screenshot_context())
            end_x, end_y = clamp_point(end_x, end_y, bounds)
            distance = math.dist((start_pos.x, start_pos.y), (end_x, end_y))
            requested_ms = duration_ms if isinstance(duration_ms, int | float) else None
            auto_ms = min(350, max(80, 45 + distance * 0.24))
            duration_ms_final = min(700, max(60, requested_ms if requested_ms is not None else auto_ms))
            duration = duration_ms_final / 1000
            steps = max(10, min(90, int(duration * 120)))
            path = human_mouse_path((start_pos.x, start_pos.y), (end_x, end_y), steps)
            self.reset()
            last = time.perf_counter()
            for index, point in enumerate(path):
                if self._stop.is_set():
                    return {"ok": False, "tool": "ospilot_move_mouse", "error": "stopped"}
                Quartz.CGWarpMouseCursorPosition(point)
                if index < len(path) - 1:
                    # Tiny cadence variation avoids a perfectly mechanical 60Hz line.
                    slice_duration = duration / steps * (0.72 + 0.56 * ((index % 5) / 4))
                    last += slice_duration
                    time.sleep(max(0.0, last - time.perf_counter()))
            final_pos = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
            final_error_px = math.dist((final_pos.x, final_pos.y), (end_x, end_y))
            return {"ok": True, "tool": "ospilot_move_mouse", "target": {"x": end_x, "y": end_y}, "metadata": {"duration_ms": round(duration * 1000), "steps": steps, "profile": "human_bezier", "final_error_px": round(final_error_px, 2)}}

    def click(self, target: dict[str, Any] | None = None, double: bool = False) -> dict:
        if target:
            moved = self.move_mouse(target, 90)
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
