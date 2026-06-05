from ospilot.desktop import create_desktop_backend
from ospilot.desktop.macos import MacOSDesktopBackend
from ospilot.desktop.windows import WindowsDesktopBackend


def test_create_desktop_backend_selects_macos(tmp_path, monkeypatch) -> None:
    from ospilot.core.config import load_config

    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    config = load_config(tmp_path / "config.yaml")

    backend = create_desktop_backend(config, "darwin")

    assert isinstance(backend, MacOSDesktopBackend)


def test_create_desktop_backend_selects_windows(tmp_path, monkeypatch) -> None:
    from ospilot.core.config import load_config

    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    config = load_config(tmp_path / "config.yaml")

    backend = create_desktop_backend(config, "win32")

    assert isinstance(backend, WindowsDesktopBackend)


def test_windows_backend_delegates_mouse_move(tmp_path, monkeypatch) -> None:
    from ospilot.core.config import load_config

    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    config = load_config(tmp_path / "config.yaml")
    backend = WindowsDesktopBackend(config)

    calls = []

    def move_mouse(target, duration_ms=None):
        calls.append((target, duration_ms))
        return {"ok": True, "tool": "ospilot_move_mouse"}

    backend.mouse.move_mouse = move_mouse
    result = backend.move_mouse({"x": 0.5, "y": 0.5}, 100)

    assert result["ok"] is True
    assert result["tool"] == "ospilot_move_mouse"
    assert calls == [({"x": 0.5, "y": 0.5}, 100)]


def test_windows_keyboard_normalizes_cross_platform_aliases() -> None:
    from ospilot.desktop.windows.keyboard import _normalize_key

    assert _normalize_key("command") == "cmd"
    assert _normalize_key("cmd") == "cmd"
    assert _normalize_key("option") == "alt"
    assert _normalize_key("control") == "ctrl"
    assert _normalize_key("AltGr") == "alt_gr"


def test_windows_shortcuts_register_altgr_hotkeys() -> None:
    from ospilot.desktop.windows.shortcuts import HOTKEYS

    assert HOTKEYS["<alt_gr>+."] == "open_chat"
    assert HOTKEYS["<ctrl>+<alt>+."] == "open_chat"
