from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OSPilotPaths:
    config_file: Path
    app_data: Path
    pi_sessions: Path
    logs_dir: Path
    log_file: Path
    pi_dir: Path
    pi_extensions: Path
    screenshots: Path


def default_paths(home: Path | None = None) -> OSPilotPaths:
    home = home or Path.home()
    app_data = home / "Library" / "Application Support" / "OSPilot"
    logs_dir = home / "Library" / "Logs" / "OSPilot"
    pi_dir = app_data / "pi"
    return OSPilotPaths(
        config_file=home / ".config" / "ospilot" / "config.yaml",
        app_data=app_data,
        pi_sessions=app_data / "pi-sessions",
        logs_dir=logs_dir,
        log_file=logs_dir / "ospilot.log",
        pi_dir=pi_dir,
        pi_extensions=pi_dir / "extensions",
        screenshots=app_data / "tmp" / "screenshots",
    )


def ensure_paths(paths: OSPilotPaths) -> None:
    for path in (
        paths.config_file.parent,
        paths.app_data,
        paths.pi_sessions,
        paths.logs_dir,
        paths.pi_dir,
        paths.pi_extensions,
        paths.screenshots,
    ):
        path.mkdir(parents=True, exist_ok=True)
