from __future__ import annotations

import os
import platform


def get_active_context() -> dict:
    return {
        "ok": True,
        "tool": "ospilot_get_active_context",
        "platform": platform.platform(),
        "frontmost_app": get_frontmost_app(),
        "mouse_position": get_mouse_position(),
    }


def get_frontmost_app() -> dict | None:
    try:
        from AppKit import NSWorkspace  # type: ignore[import-not-found]

        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return None
        pid = int(app.processIdentifier())
        return {
            "name": str(app.localizedName() or ""),
            "pid": pid,
            "is_self": pid == os.getpid(),
        }
    except Exception:
        return None


def focus_app(pid: int) -> dict:
    try:
        from AppKit import NSApplicationActivateIgnoringOtherApps, NSRunningApplication  # type: ignore[import-not-found]

        if pid <= 0 or pid == os.getpid():
            return {"ok": False, "tool": "ospilot_focus_app", "error": "invalid target app pid"}
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        if app is None:
            return {"ok": False, "tool": "ospilot_focus_app", "error": f"app not found for pid {pid}"}
        ok = bool(app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps))
        return {"ok": ok, "tool": "ospilot_focus_app", "app": {"pid": pid, "name": str(app.localizedName() or "")}}
    except Exception as exc:
        return {"ok": False, "tool": "ospilot_focus_app", "error": str(exc)}


def get_mouse_position() -> dict[str, float] | None:
    try:
        import Quartz

        event = Quartz.CGEventCreate(None)
        pos = Quartz.CGEventGetLocation(event)
        return {"x": pos.x, "y": pos.y}
    except Exception:
        return None
