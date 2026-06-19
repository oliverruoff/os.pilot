from __future__ import annotations

import os
import shlex
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .paths import OSPilotPaths, default_paths, ensure_paths


@dataclass(frozen=True)
class PrivacyConfig:
    store_screenshots: bool = False
    store_conversations: bool = False
    redact_secrets_best_effort: bool = True
    debug_mode: bool = False


@dataclass(frozen=True)
class PiConfig:
    executable: str = "pi"
    args: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class UIConfig:
    mouse_move_debug_teleport: bool = False


@dataclass(frozen=True)
class AppConfig:
    paths: OSPilotPaths
    pi: PiConfig = field(default_factory=PiConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    ui: UIConfig = field(default_factory=UIConfig)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    loaded = yaml.safe_load(path.read_text())
    return loaded if isinstance(loaded, dict) else {}


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _default_pi_executable() -> str:
    if sys.platform == "win32":
        return shutil.which("pi.cmd") or shutil.which("pi") or "pi.cmd"
    return "pi"


def _resolve_pi_executable(value: Any) -> str:
    executable = str(value or _default_pi_executable())
    if sys.platform == "win32" and executable.lower() == "pi":
        return shutil.which("pi.cmd") or shutil.which("pi") or "pi.cmd"
    return executable


def load_config(path: Path | None = None) -> AppConfig:
    _load_env_file(Path.cwd() / ".env")
    paths = default_paths()
    ensure_paths(paths)
    _load_env_file(paths.config_file.parent / ".env")
    data = _read_yaml(path or paths.config_file)

    pi_data = data.get("pi", {}) if isinstance(data.get("pi", {}), dict) else {}
    privacy_data = data.get("privacy", {}) if isinstance(data.get("privacy", {}), dict) else {}
    ui_data = data.get("ui", {}) if isinstance(data.get("ui", {}), dict) else {}

    pi_args = list(pi_data.get("args", []))
    if env_args := os.environ.get("PI_ARGS"):
        pi_args.extend(shlex.split(env_args))

    return AppConfig(
        paths=paths,
        pi=PiConfig(executable=_resolve_pi_executable(pi_data.get("executable")), args=pi_args),
        privacy=PrivacyConfig(
            store_screenshots=bool(privacy_data.get("store_screenshots", False)),
            store_conversations=bool(privacy_data.get("store_conversations", False)),
            redact_secrets_best_effort=bool(privacy_data.get("redact_secrets_best_effort", True)),
            debug_mode=bool(privacy_data.get("debug_mode", False)),
        ),
        ui=UIConfig(mouse_move_debug_teleport=bool(ui_data.get("mouse_move_debug_teleport", False))),
    )


def pi_environment(config: AppConfig, extra: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["PI_CODING_AGENT_SESSION_DIR"] = str(config.paths.pi_sessions)
    if extra:
        env.update(extra)
    return env
