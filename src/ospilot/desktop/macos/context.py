from __future__ import annotations

import platform


def get_active_context() -> dict:
    return {
        "ok": True,
        "tool": "ospilot_get_active_context",
        "platform": platform.platform(),
        "mouse_position": get_mouse_position(),
    }


def get_mouse_position() -> dict[str, float] | None:
    try:
        import Quartz

        event = Quartz.CGEventCreate(None)
        pos = Quartz.CGEventGetLocation(event)
        return {"x": pos.x, "y": pos.y}
    except Exception:
        return None
