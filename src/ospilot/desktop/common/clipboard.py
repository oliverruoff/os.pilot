from __future__ import annotations

def read_clipboard() -> dict:
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance()
    if app is None:
        return {"ok": False, "tool": "ospilot_read_clipboard", "error": "QGuiApplication is required"}
    return {"ok": True, "tool": "ospilot_read_clipboard", "text": app.clipboard().text()}


def write_clipboard(text: str) -> dict:
    from PySide6.QtGui import QGuiApplication

    app = QGuiApplication.instance()
    if app is None:
        return {"ok": False, "tool": "ospilot_write_clipboard", "error": "QGuiApplication is required"}
    app.clipboard().setText(text)
    return {"ok": True, "tool": "ospilot_write_clipboard"}
