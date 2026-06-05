from __future__ import annotations

import sys
from typing import Any


def allow_fullscreen_overlay(widget: Any, nonactivating: bool = True) -> None:
    if sys.platform == "darwin":
        from ospilot.desktop.macos.window import allow_fullscreen_overlay as platform_allow_fullscreen_overlay
    elif sys.platform == "win32":
        from ospilot.desktop.windows.window import allow_fullscreen_overlay as platform_allow_fullscreen_overlay
    else:
        return
    platform_allow_fullscreen_overlay(widget, nonactivating)


def order_front(widget: Any, make_key: bool = False) -> None:
    if sys.platform == "darwin":
        from ospilot.desktop.macos.window import order_front as platform_order_front
    elif sys.platform == "win32":
        from ospilot.desktop.windows.window import order_front as platform_order_front
    else:
        return
    platform_order_front(widget, make_key)
