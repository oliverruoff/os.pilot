from __future__ import annotations

import os
import platform
import sys
from ctypes import POINTER, Structure, byref, create_unicode_buffer, wintypes
from typing import Any


class POINT(Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def get_active_context() -> dict[str, Any]:
    try:
        user32, _kernel32 = _win32()
        point = POINT()
        mouse_position = None
        if user32.GetCursorPos(byref(point)):
            mouse_position = {"x": int(point.x), "y": int(point.y)}

        hwnd = user32.GetForegroundWindow()
        app = _window_app(hwnd) if hwnd else None
        return {"ok": True, "tool": "ospilot_get_active_context", "platform": platform.platform(), "mouse_position": mouse_position, "frontmost_app": app}
    except Exception as exc:
        return {"ok": False, "tool": "ospilot_get_active_context", "platform": "windows", "error": str(exc)}


def focus_app(pid: int) -> dict[str, Any]:
    tool = "ospilot_focus_app"
    try:
        hwnd = _top_level_window_for_pid(pid)
        if not hwnd:
            return {"ok": False, "tool": tool, "error": f"no visible window found for pid {pid}"}

        user32, _kernel32 = _win32()
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        return {"ok": True, "tool": tool, "pid": pid, "hwnd": int(hwnd)}
    except Exception as exc:
        return {"ok": False, "tool": tool, "error": str(exc)}


def _win32():
    if sys.platform != "win32":
        raise RuntimeError("Windows desktop APIs require win32")
    import ctypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.GetCursorPos.argtypes = [POINTER(POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL
    user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.ShowWindow.restype = wintypes.BOOL
    user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM), wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, POINTER(wintypes.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return user32, kernel32


def _window_app(hwnd: int) -> dict[str, Any] | None:
    user32, _kernel32 = _win32()
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, byref(pid))
    title = _window_title(hwnd)
    path = _process_path(int(pid.value))
    name = os.path.basename(path) if path else title
    return {"pid": int(pid.value), "name": name, "window_title": title, "executable": path, "hwnd": int(hwnd), "is_self": int(pid.value) == os.getpid()}


def _window_title(hwnd: int) -> str:
    user32, _kernel32 = _win32()
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _process_path(pid: int) -> str:
    if pid <= 0:
        return ""
    import ctypes

    _user32, kernel32 = _win32()
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buffer = create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, byref(size)):
            return buffer.value
        return ""
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def _top_level_window_for_pid(pid: int) -> int | None:
    import ctypes

    user32, _kernel32 = _win32()
    found: list[int] = []

    enum_proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        window_pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, byref(window_pid))
        if int(window_pid.value) == pid and _window_title(hwnd):
            found.append(int(hwnd))
            return False
        return True

    user32.EnumWindows(enum_proc_type(callback), 0)
    return found[0] if found else None
