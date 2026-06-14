from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

from ospilot.core.config import AppConfig
from ospilot.desktop.common.screenshots import hd_screenshot_size


_LAST_SCREENSHOT_CONTEXT: dict | None = None


def get_last_screenshot_context() -> dict | None:
    return _LAST_SCREENSHOT_CONTEXT


def capture_screenshot_current_mouse_monitor(config: AppConfig) -> dict:
    try:
        import Quartz
    except Exception as exc:
        return {"ok": False, "tool": "ospilot_capture_screenshot_current_mouse_monitor", "error": str(exc)}

    event = Quartz.CGEventCreate(None)
    cursor = Quartz.CGEventGetLocation(event)
    display_id, bounds, pixels_wide, pixels_high = _display_for_point(Quartz, cursor.x, cursor.y)
    if display_id is None or bounds is None:
        return {"ok": False, "tool": "ospilot_capture_screenshot_current_mouse_monitor", "error": "no screen found"}

    target_dir = config.paths.screenshots if config.privacy.store_screenshots else Path(tempfile.gettempdir())
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time() * 1000)
    path = target_dir / f"ospilot-screenshot-{timestamp}.jpg"
    raw_path = target_dir / f"ospilot-screenshot-raw-{timestamp}.png"

    x = int(bounds.origin.x)
    y = int(bounds.origin.y)
    width = int(bounds.size.width)
    height = int(bounds.size.height)

    started = time.perf_counter()
    result = subprocess.run(
        ["screencapture", "-x", "-R", f"{x},{y},{width},{height}", str(raw_path)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    captured_at = time.perf_counter()
    if result.returncode != 0:
        return {"ok": False, "tool": "ospilot_capture_screenshot_current_mouse_monitor", "error": result.stderr.strip() or "screencapture failed"}

    scaled_width, scaled_height = hd_screenshot_size(pixels_wide, pixels_high)
    convert = subprocess.run(
        [
            "sips",
            "--resampleHeightWidth",
            str(scaled_height),
            str(scaled_width),
            "-s",
            "format",
            "jpeg",
            "-s",
            "formatOptions",
            "45",
            str(raw_path),
            "--out",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    resized_at = time.perf_counter()
    if convert.returncode != 0:
        try:
            raw_path.unlink(missing_ok=True)
        except Exception:
            pass
        return {"ok": False, "tool": "ospilot_capture_screenshot_current_mouse_monitor", "error": convert.stderr.strip() or "screenshot resize failed"}
    try:
        raw_path.unlink(missing_ok=True)
    except Exception:
        pass

    result = {
        "ok": True,
        "tool": "ospilot_capture_screenshot_current_mouse_monitor",
        "mouse_position": {"x": cursor.x, "y": cursor.y},
        "monitor_bounds": {"x": x, "y": y, "width": width, "height": height},
        "screenshot_size": {"width": int(scaled_width), "height": int(scaled_height)},
        "original_screenshot_size": {"width": int(pixels_wide), "height": int(pixels_high)},
        "screenshot_path": str(path),
        "screenshot_mime_type": "image/jpeg",
        "scale_factor": float(scaled_width / width) if width else 1.0,
        "original_scale_factor": float(pixels_wide / width) if width else 1.0,
        "metadata": {
            "capture_ms": round((captured_at - started) * 1000),
            "resize_encode_ms": round((resized_at - captured_at) * 1000),
            "bytes": path.stat().st_size if path.exists() else 0,
        },
    }
    global _LAST_SCREENSHOT_CONTEXT
    _LAST_SCREENSHOT_CONTEXT = result
    return result


def _display_for_point(Quartz, x: float, y: float):
    err, displays, count = Quartz.CGGetActiveDisplayList(32, None, None)
    if err != 0:
        return None, None, 0, 0
    for display_id in displays[:count]:
        bounds = Quartz.CGDisplayBounds(display_id)
        if bounds.origin.x <= x <= bounds.origin.x + bounds.size.width and bounds.origin.y <= y <= bounds.origin.y + bounds.size.height:
            return display_id, bounds, Quartz.CGDisplayPixelsWide(display_id), Quartz.CGDisplayPixelsHigh(display_id)
    if count:
        display_id = displays[0]
        bounds = Quartz.CGDisplayBounds(display_id)
        return display_id, bounds, Quartz.CGDisplayPixelsWide(display_id), Quartz.CGDisplayPixelsHigh(display_id)
    return None, None, 0, 0
