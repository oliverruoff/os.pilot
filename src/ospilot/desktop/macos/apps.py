from __future__ import annotations

import subprocess


def open_app(app_name: str) -> dict:
    result = subprocess.run(["open", "-a", app_name], capture_output=True, text=True, timeout=20)
    return {"ok": result.returncode == 0, "tool": "ospilot_open_app", "stderr": result.stderr, "metadata": {"exit_code": result.returncode}}
