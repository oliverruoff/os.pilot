from __future__ import annotations

import sys

from ospilot.core.config import AppConfig

from .backend import DesktopBackend


def create_desktop_backend(config: AppConfig, platform: str | None = None) -> DesktopBackend:
    platform = platform or sys.platform
    if platform == "darwin":
        from .macos.backend import MacOSDesktopBackend

        return MacOSDesktopBackend(config)
    if platform == "win32":
        from .windows.backend import WindowsDesktopBackend

        return WindowsDesktopBackend(config)
    raise RuntimeError(f"unsupported platform: {platform}")


__all__ = ["DesktopBackend", "create_desktop_backend"]
