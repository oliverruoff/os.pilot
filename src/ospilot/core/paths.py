from __future__ import annotations

import os
import sys
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
    screenshots: Path
    source_root: Path
    pi_tools_source: Path
    pi_desktop_tools_extension: Path
    pi_skills_source: Path


def default_paths(home: Path | None = None) -> OSPilotPaths:
    home = home or Path.home()
    source_root = Path(__file__).resolve().parents[3]
    config_file, app_data, logs_dir = _platform_base_paths(home)
    pi_dir = app_data / "pi"
    return OSPilotPaths(
        config_file=config_file,
        app_data=app_data,
        pi_sessions=app_data / "pi-sessions",
        logs_dir=logs_dir,
        log_file=logs_dir / "ospilot.log",
        pi_dir=pi_dir,
        screenshots=app_data / "tmp" / "screenshots",
        source_root=source_root,
        pi_tools_source=source_root / "pi" / "tools",
        pi_desktop_tools_extension=source_root / "pi" / "tools" / "ospilot-desktop-tools.ts",
        pi_skills_source=source_root / "pi" / "skills",
    )


def _platform_base_paths(home: Path) -> tuple[Path, Path, Path]:
    if sys.platform == "win32":
        roaming = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        return roaming / "OSPilot" / "config.yaml", local / "OSPilot", local / "OSPilot" / "Logs"
    if sys.platform == "darwin":
        return (
            home / ".config" / "ospilot" / "config.yaml",
            home / "Library" / "Application Support" / "OSPilot",
            home / "Library" / "Logs" / "OSPilot",
        )
    return (
        home / ".config" / "ospilot" / "config.yaml",
        home / ".local" / "share" / "ospilot",
        home / ".local" / "state" / "ospilot" / "logs",
    )


def ensure_paths(paths: OSPilotPaths) -> None:
    for path in (
        paths.config_file.parent,
        paths.app_data,
        paths.pi_sessions,
        paths.logs_dir,
        paths.pi_dir,
        paths.screenshots,
    ):
        path.mkdir(parents=True, exist_ok=True)
