from __future__ import annotations

import sys
from ctypes import c_void_p
from typing import Any


def _ns_window_for_widget(widget: Any) -> Any | None:
    if sys.platform != "darwin":
        return None

    try:
        import objc  # type: ignore[import-not-found]
    except Exception:
        return None

    try:
        # winId() forces Qt to create the native NSWindow.  We intentionally do
        # this before the first show so Space/full-screen behavior is installed
        # before AppKit has a chance to move to OSPilot's original Space.
        handle = int(widget.winId())
        native = objc.objc_object(c_void_p=handle)
        return native.window() if hasattr(native, "window") else native
    except Exception:
        return None


def configure_background_app() -> None:
    """Keep OSPilot from behaving like a normal foreground macOS app."""
    if sys.platform != "darwin":
        return
    try:
        from AppKit import NSApp, NSApplicationActivationPolicyAccessory  # type: ignore[import-not-found]

        if NSApp() is not None:
            NSApp().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except Exception:
        return


def allow_fullscreen_overlay(widget: Any, nonactivating: bool = True) -> None:
    """Make a Qt top-level widget behave like a macOS overlay.

    Qt's WindowStaysOnTopHint is not enough on macOS: full-screen apps live in
    their own Spaces.  The overlay must join the active Space before it is shown;
    otherwise activating OSPilot can jump the user back to the Space/Desktop
    where OSPilot was launched.
    """
    if sys.platform != "darwin":
        return

    try:
        import AppKit  # type: ignore[import-not-found]
        from AppKit import (  # type: ignore[import-not-found]
            NSFloatingWindowLevel,
            NSWindowCollectionBehaviorCanJoinAllSpaces,
            NSWindowCollectionBehaviorFullScreenAuxiliary,
            NSWindowCollectionBehaviorIgnoresCycle,
            NSWindowCollectionBehaviorTransient,
        )
    except Exception:
        return

    try:
        ns_window = _ns_window_for_widget(widget)
        if ns_window is None:
            return

        behavior = ns_window.collectionBehavior()
        behavior |= NSWindowCollectionBehaviorCanJoinAllSpaces
        behavior |= NSWindowCollectionBehaviorFullScreenAuxiliary
        behavior |= NSWindowCollectionBehaviorTransient
        behavior |= NSWindowCollectionBehaviorIgnoresCycle
        behavior |= getattr(AppKit, "NSWindowCollectionBehaviorMoveToActiveSpace", 0)
        ns_window.setCollectionBehavior_(behavior)
        ns_window.setLevel_(NSFloatingWindowLevel)
        if hasattr(ns_window, "setHidesOnDeactivate_"):
            ns_window.setHidesOnDeactivate_(False)

        # Prevent AppKit from activating OSPilot and switching Spaces for
        # passive overlays. Chat input windows opt out so the QLineEdit can
        # receive keyboard focus.
        nonactivating_mask = getattr(AppKit, "NSWindowStyleMaskNonactivatingPanel", 1 << 7)
        if hasattr(ns_window, "styleMask") and hasattr(ns_window, "setStyleMask_"):
            style = ns_window.styleMask()
            if nonactivating:
                style |= nonactivating_mask
            else:
                style &= ~nonactivating_mask
            ns_window.setStyleMask_(style)
    except Exception:
        return


def order_front(widget: Any, make_key: bool = False) -> None:
    """Show an already-created overlay without asking macOS to change Spaces."""
    ns_window = _ns_window_for_widget(widget)
    if ns_window is None:
        return
    try:
        if make_key:
            # For full-screen Spaces, first join/order into the active Space,
            # then ask AppKit to make this window key. This avoids Qt's generic
            # activation path, which can jump back to OSPilot's launch Desktop.
            ns_window.orderFrontRegardless()
            if hasattr(ns_window, "makeKeyAndOrderFront_"):
                ns_window.makeKeyAndOrderFront_(None)
            elif hasattr(ns_window, "makeKeyWindow"):
                ns_window.makeKeyWindow()
        else:
            ns_window.orderFrontRegardless()
    except Exception:
        return


def focus_widget(widget: Any, top_level: Any | None = None) -> None:
    """Make a Qt child widget first responder without Qt app activation."""
    if sys.platform != "darwin":
        return
    try:
        import objc  # type: ignore[import-not-found]
    except Exception:
        return
    try:
        int((top_level or widget).winId())
        handle = int(widget.winId())
        native = objc.objc_object(c_void_p=handle)
        ns_view = native.contentView() if hasattr(native, "contentView") else native
        ns_window = (
            ns_view.window()
            if hasattr(ns_view, "window")
            else _ns_window_for_widget(top_level or widget)
        )
        if ns_window is not None and hasattr(ns_window, "makeFirstResponder_"):
            ns_window.makeFirstResponder_(ns_view)
    except Exception:
        return
