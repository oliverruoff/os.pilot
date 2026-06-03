from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

from ospilot.config import AppConfig


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
    path = target_dir / f"ospilot-screenshot-{int(time.time() * 1000)}.png"

    x = int(bounds.origin.x)
    y = int(bounds.origin.y)
    width = int(bounds.size.width)
    height = int(bounds.size.height)

    result = subprocess.run(
        ["screencapture", "-x", "-R", f"{x},{y},{width},{height}", str(path)],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        return {"ok": False, "tool": "ospilot_capture_screenshot_current_mouse_monitor", "error": result.stderr.strip() or "screencapture failed"}

    return {
        "ok": True,
        "tool": "ospilot_capture_screenshot_current_mouse_monitor",
        "screenshot_path": str(path),
        "mouse_position": {"x": cursor.x, "y": cursor.y},
        "monitor_bounds": {"x": x, "y": y, "width": width, "height": height},
        "screenshot_size": {"width": int(pixels_wide), "height": int(pixels_high)},
        "scale_factor": float(pixels_wide / width) if width else 1.0,
    }


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
