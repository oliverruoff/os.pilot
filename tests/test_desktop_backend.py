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


def test_windows_backend_returns_controlled_stub(tmp_path, monkeypatch) -> None:
    from ospilot.core.config import load_config

    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    config = load_config(tmp_path / "config.yaml")
    backend = WindowsDesktopBackend(config)

    result = backend.move_mouse({"x": 0.5, "y": 0.5})

    assert result["ok"] is False
    assert result["tool"] == "ospilot_move_mouse"
    assert result["platform"] == "windows"
    assert "not implemented" in result["error"]
