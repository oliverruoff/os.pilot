from __future__ import annotations

import subprocess
import sys


def open_app(app_name: str) -> dict:
    tool = "ospilot_open_app"
    app_name = app_name.strip()
    if not app_name:
        return {"ok": False, "tool": tool, "error": "app_name must not be empty"}
    try:
        if sys.platform == "win32":
            import ctypes

            result = ctypes.windll.shell32.ShellExecuteW(None, "open", app_name, None, None, 1)
            if int(result) > 32:
                return {"ok": True, "tool": tool, "metadata": {"method": "ShellExecuteW", "result": int(result)}}
        process = subprocess.Popen([app_name])
        return {"ok": True, "tool": tool, "metadata": {"method": "Popen", "pid": process.pid}}
    except Exception as exc:
        return {"ok": False, "tool": tool, "error": str(exc)}
