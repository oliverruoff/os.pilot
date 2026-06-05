from __future__ import annotations

from typing import Any

from .context import _window_app, _win32


CONTROL_TYPES = {
    50000: "Button",
    50001: "Calendar",
    50002: "CheckBox",
    50003: "ComboBox",
    50004: "Edit",
    50005: "Hyperlink",
    50006: "Image",
    50007: "ListItem",
    50008: "List",
    50009: "Menu",
    50010: "MenuBar",
    50011: "MenuItem",
    50012: "ProgressBar",
    50013: "RadioButton",
    50014: "ScrollBar",
    50015: "Slider",
    50016: "Spinner",
    50017: "StatusBar",
    50018: "Tab",
    50019: "TabItem",
    50020: "Text",
    50023: "Tree",
    50024: "TreeItem",
    50025: "Custom",
    50026: "Group",
    50030: "Document",
}

INTERESTING_ROLES = {"Button", "CheckBox", "ComboBox", "Edit", "Hyperlink", "Image", "MenuItem", "RadioButton", "TabItem", "Text"}


def get_frontmost_ui_elements(query: str = "", limit: int = 120) -> dict[str, Any]:
    tool = "ospilot_get_frontmost_ui_elements"
    try:
        import comtypes.client
    except Exception as exc:
        return {"ok": False, "tool": tool, "error": f"Windows UI Automation dependency unavailable: {exc}"}

    try:
        user32, _kernel32 = _win32()
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {"ok": False, "tool": tool, "error": "no foreground window"}
        automation = comtypes.client.CreateObject("UIAutomationClient.CUIAutomation")
        root = automation.ElementFromHandle(hwnd)
        condition = automation.CreateTrueCondition()
        collection = root.FindAll(4, condition)  # TreeScope_Descendants
        query_l = query.casefold().strip()
        found: list[dict[str, Any]] = []

        count = min(int(getattr(collection, "Length", 0)), max(limit * 20, limit))
        for index in range(count):
            if len(found) >= limit:
                break
            element = collection.GetElement(index)
            item = _element_dict(element)
            if not item:
                continue
            haystack = " ".join(str(item.get(key, "")) for key in ("role", "label", "title", "description", "value")).casefold()
            if query_l and not (query_l in haystack or all(token in haystack for token in query_l.split())):
                continue
            if item["role"] not in INTERESTING_ROLES and not query_l:
                continue
            found.append(item)

        return {"ok": True, "tool": tool, "app": _window_app(hwnd), "query": query, "count": len(found), "elements": found}
    except Exception as exc:
        return {"ok": False, "tool": tool, "error": str(exc)}


def _element_dict(element: Any) -> dict[str, Any] | None:
    try:
        rect = element.CurrentBoundingRectangle
        left = float(rect.left)
        top = float(rect.top)
        width = float(rect.right - rect.left)
        height = float(rect.bottom - rect.top)
        if width <= 1 or height <= 1:
            return None
        title = _text(getattr(element, "CurrentName", ""))
        description = _text(getattr(element, "CurrentHelpText", ""))
        value = _text(_value_text(element))
        label = title or description or value
        if not label:
            return None
        role = CONTROL_TYPES.get(int(getattr(element, "CurrentControlType", 0)), str(getattr(element, "CurrentControlType", "")))
        return {
            "role": role,
            "label": label[:160],
            "title": title[:160],
            "description": description[:160],
            "value": value[:160],
            "bounds": {"x": round(left, 2), "y": round(top, 2), "width": round(width, 2), "height": round(height, 2)},
            "center": {"x": round(left + width / 2, 2), "y": round(top + height / 2, 2)},
        }
    except Exception:
        return None


def _value_text(element: Any) -> str:
    try:
        pattern = element.GetCurrentPattern(10002)  # UIA_ValuePatternId
        return str(pattern.CurrentValue)
    except Exception:
        return ""


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()
