from __future__ import annotations

import subprocess
import time


def run_shell_command(command: str, cwd: str | None = None) -> dict:
    start = time.monotonic()
    result = subprocess.run(command, cwd=cwd, shell=True, capture_output=True, text=True, timeout=120)
    return {
        "ok": result.returncode == 0,
        "tool": "ospilot_run_shell_command",
        "stdout": result.stdout,
        "stderr": result.stderr,
        "metadata": {"exit_code": result.returncode, "duration_ms": round((time.monotonic() - start) * 1000)},
    }
