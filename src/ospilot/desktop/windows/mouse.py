from __future__ import annotations

import math
import threading
import time
from typing import Any

from ospilot.desktop.common.coordinates import Bounds, clamp_point, human_mouse_path, normalize_target

from .screenshot import get_last_screenshot_context


class MouseController:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._lock = threading.Lock()

    def stop(self) -> None:
        self._stop.set()

    def reset(self) -> None:
        self._stop.clear()

    def move_mouse(self, target: dict[str, Any], duration_ms: int | None = None) -> dict[str, Any]:
        tool = "ospilot_move_mouse"
        try:
            from pynput.mouse import Controller
        except Exception as exc:
            return {"ok": False, "tool": tool, "error": f"pynput mouse unavailable: {exc}"}

        with self._lock:
            try:
                mouse = Controller()
                start_x, start_y = _cursor_position()
                bounds = _monitor_bounds_for_point(start_x, start_y)
                end_x, end_y = normalize_target(target, bounds, get_last_screenshot_context())
                end_x, end_y = clamp_point(end_x, end_y, bounds)
                distance = math.dist((start_x, start_y), (end_x, end_y))
                requested_ms = duration_ms if isinstance(duration_ms, int | float) else None
                auto_ms = min(350, max(80, 45 + distance * 0.24))
                duration_ms_final = min(700, max(60, requested_ms if requested_ms is not None else auto_ms))
                duration = duration_ms_final / 1000
                steps = max(10, min(90, int(duration * 120)))
                path = human_mouse_path((start_x, start_y), (end_x, end_y), steps)
                self.reset()
                last = time.perf_counter()
                for index, point in enumerate(path):
                    if self._stop.is_set():
                        return {"ok": False, "tool": tool, "error": "stopped"}
                    _set_cursor_position(round(point[0]), round(point[1]), mouse)
                    if index < len(path) - 1:
                        slice_duration = duration / steps * (0.72 + 0.56 * ((index % 5) / 4))
                        last += slice_duration
                        time.sleep(max(0.0, last - time.perf_counter()))
                _set_cursor_position(round(end_x), round(end_y), mouse)
                final_x, final_y = _cursor_position()
                final_error_px = math.dist((final_x, final_y), (end_x, end_y))
                return {"ok": True, "tool": tool, "target": {"x": end_x, "y": end_y}, "metadata": {"duration_ms": round(duration * 1000), "steps": steps, "profile": "human_bezier", "final_error_px": round(final_error_px, 2)}}
            except Exception as exc:
                return {"ok": False, "tool": tool, "error": str(exc)}

    def click(self, target: dict[str, Any] | None = None, double: bool = False) -> dict[str, Any]:
        return self._click(target, button="left", double=double)

    def right_click(self, target: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._click(target, button="right", double=False)

    def _click(self, target: dict[str, Any] | None = None, button: str = "left", double: bool = False) -> dict[str, Any]:
        tool = _click_tool(button, double)
        if target:
            moved = self.move_mouse(target, 90)
            if not moved.get("ok"):
                return moved
            time.sleep(0.06)
        try:
            from pynput.mouse import Button, Controller

            mouse = Controller()
            pynput_button = Button.right if button == "right" else Button.left
            mouse.click(pynput_button, 2 if double else 1)
            x, y = _cursor_position()
            return {"ok": True, "tool": tool, "target": {"x": x, "y": y}, "metadata": {"button": button}}
        except Exception as exc:
            return {"ok": False, "tool": tool, "error": str(exc)}


def _click_tool(button: str, double: bool) -> str:
    if button == "right":
        return "ospilot_right_click"
    return "ospilot_double_click" if double else "ospilot_click"


def _monitor_bounds_for_point(x: float, y: float) -> Bounds:
    try:
        import mss

        with mss.mss() as sct:
            monitors = sct.monitors[1:] or sct.monitors[:1]
            for monitor in monitors:
                left = float(monitor["left"])
                top = float(monitor["top"])
                width = float(monitor["width"])
                height = float(monitor["height"])
                if left <= x <= left + width and top <= y <= top + height:
                    return Bounds(left, top, width, height)
            if monitors:
                monitor = monitors[0]
                return Bounds(float(monitor["left"]), float(monitor["top"]), float(monitor["width"]), float(monitor["height"]))
    except Exception:
        pass
    return Bounds(0, 0, 1920, 1080)


def _cursor_position() -> tuple[int, int]:
    try:
        import ctypes
        from ctypes import Structure, byref, wintypes

        class POINT(Structure):
            _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

        ctypes.windll.user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
        ctypes.windll.user32.GetCursorPos.restype = wintypes.BOOL
        point = POINT()
        if ctypes.windll.user32.GetCursorPos(byref(point)):
            return int(point.x), int(point.y)
    except Exception:
        pass

    from pynput.mouse import Controller

    x, y = Controller().position
    return int(x), int(y)


def _set_cursor_position(x: int, y: int, mouse=None) -> None:
    try:
        import ctypes

        ctypes.windll.user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        ctypes.windll.user32.SetCursorPos.restype = ctypes.c_bool
        if ctypes.windll.user32.SetCursorPos(int(x), int(y)):
            return
    except Exception:
        pass

    if mouse is None:
        from pynput.mouse import Controller

        mouse = Controller()
    mouse.position = (int(x), int(y))
