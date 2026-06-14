from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any

from ospilot.core.config import AppConfig
from ospilot.desktop.common.screenshots import hd_screenshot_size


_LAST_SCREENSHOT_CONTEXT: dict[str, Any] | None = None


def get_last_screenshot_context() -> dict[str, Any] | None:
    return _LAST_SCREENSHOT_CONTEXT


def capture_screenshot_current_mouse_monitor(config: AppConfig) -> dict[str, Any]:
    tool = "ospilot_capture_screenshot_current_mouse_monitor"
    try:
        import mss
        from PIL import Image
    except Exception as exc:
        return {"ok": False, "tool": tool, "error": f"Windows screenshot dependencies unavailable: {exc}"}

    try:
        with mss.mss() as sct:
            cursor_x, cursor_y = _cursor_position()
            monitor = _monitor_for_point(sct.monitors[1:], cursor_x, cursor_y)
            if not monitor:
                return {"ok": False, "tool": tool, "error": "no screen found"}

            target_dir = config.paths.screenshots if config.privacy.store_screenshots else Path(tempfile.gettempdir())
            target_dir.mkdir(parents=True, exist_ok=True)
            path = target_dir / f"ospilot-screenshot-{int(time.time() * 1000)}.jpg"
            started = time.perf_counter()
            raw = sct.grab(monitor)
            captured_at = time.perf_counter()
            image = Image.frombytes("RGB", raw.size, raw.rgb)
            scaled_width, scaled_height = hd_screenshot_size(raw.width, raw.height)
            if image.size != (scaled_width, scaled_height):
                resampling = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
                image = image.resize((scaled_width, scaled_height), resampling)
            image.save(path, format="JPEG", quality=45, optimize=False, subsampling=2)
            encoded_at = time.perf_counter()

            result: dict[str, Any] = {
                "ok": True,
                "tool": tool,
                "mouse_position": {"x": cursor_x, "y": cursor_y},
                "monitor_bounds": {"x": int(monitor["left"]), "y": int(monitor["top"]), "width": int(monitor["width"]), "height": int(monitor["height"])},
                "screenshot_size": {"width": int(scaled_width), "height": int(scaled_height)},
                "original_screenshot_size": {"width": int(raw.width), "height": int(raw.height)},
                "screenshot_path": str(path),
                "screenshot_mime_type": "image/jpeg",
                "scale_factor": float(scaled_width / monitor["width"]) if monitor["width"] else 1.0,
                "original_scale_factor": float(raw.width / monitor["width"]) if monitor["width"] else 1.0,
                "metadata": {
                    "capture_ms": round((captured_at - started) * 1000),
                    "resize_encode_ms": round((encoded_at - captured_at) * 1000),
                    "bytes": path.stat().st_size if path.exists() else 0,
                },
            }
            global _LAST_SCREENSHOT_CONTEXT
            _LAST_SCREENSHOT_CONTEXT = result
            return result
    except Exception as exc:
        return {"ok": False, "tool": tool, "error": str(exc)}


def _cursor_position() -> tuple[int, int]:
    import ctypes
    from ctypes import Structure, byref, wintypes

    class POINT(Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    ctypes.windll.user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    ctypes.windll.user32.GetCursorPos.restype = wintypes.BOOL
    point = POINT()
    if not ctypes.windll.user32.GetCursorPos(byref(point)):
        raise RuntimeError("GetCursorPos failed")
    return int(point.x), int(point.y)


def _monitor_for_point(monitors: list[dict[str, int]], x: int, y: int) -> dict[str, int] | None:
    for monitor in monitors:
        left = int(monitor["left"])
        top = int(monitor["top"])
        width = int(monitor["width"])
        height = int(monitor["height"])
        if left <= x <= left + width and top <= y <= top + height:
            return monitor
    return monitors[0] if monitors else None
