from __future__ import annotations

from typing import Any


INTERESTING_ROLES = {
    "AXButton",
    "AXCheckBox",
    "AXComboBox",
    "AXImage",
    "AXLink",
    "AXMenuButton",
    "AXMenuItem",
    "AXPopUpButton",
    "AXRadioButton",
    "AXSearchField",
    "AXStaticText",
    "AXTabGroup",
    "AXTextField",
}


def get_frontmost_ui_elements(query: str = "", limit: int = 120) -> dict[str, Any]:
    """Return visible Accessibility UI elements for the frontmost macOS app.

    This is much faster and more precise than asking the model to infer element
    positions from a screenshot. Coordinates are macOS global display points.
    """
    try:
        import ApplicationServices as AX
        from AppKit import NSWorkspace
    except Exception as exc:
        return {"ok": False, "tool": "ospilot_get_frontmost_ui_elements", "error": str(exc)}

    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None:
        return {"ok": False, "tool": "ospilot_get_frontmost_ui_elements", "error": "no frontmost app"}

    pid = int(app.processIdentifier())
    root = AX.AXUIElementCreateApplication(pid)
    query_l = query.casefold().strip()
    found: list[dict[str, Any]] = []
    seen: set[int] = set()

    def attr(element: Any, name: str) -> Any:
        try:
            err, value = AX.AXUIElementCopyAttributeValue(element, name, None)
            return value if err == 0 else None
        except Exception:
            return None

    def point(value: Any) -> tuple[float, float] | None:
        if value is None:
            return None
        try:
            ok, point_value = AX.AXValueGetValue(value, AX.kAXValueCGPointType, None)
            if ok:
                return float(point_value.x), float(point_value.y)
        except Exception:
            return None
        return None

    def size(value: Any) -> tuple[float, float] | None:
        if value is None:
            return None
        try:
            ok, size_value = AX.AXValueGetValue(value, AX.kAXValueCGSizeType, None)
            if ok:
                return float(size_value.width), float(size_value.height)
        except Exception:
            return None
        return None

    def text_value(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    def visit(element: Any, depth: int = 0) -> None:
        if len(found) >= limit or depth > 10:
            return
        key = id(element)
        if key in seen:
            return
        seen.add(key)

        role = text_value(attr(element, AX.kAXRoleAttribute))
        title = text_value(attr(element, AX.kAXTitleAttribute))
        description = text_value(attr(element, AX.kAXDescriptionAttribute))
        value = text_value(attr(element, AX.kAXValueAttribute))
        label = title or description or value
        haystack = " ".join(part for part in (role, title, description, value) if part).casefold()

        pos = point(attr(element, AX.kAXPositionAttribute))
        sz = size(attr(element, AX.kAXSizeAttribute))
        if pos and sz and sz[0] > 1 and sz[1] > 1 and label and (not query_l or query_l in haystack or all(token in haystack for token in query_l.split())):
            x, y = pos
            width, height = sz
            if role in INTERESTING_ROLES or query_l:
                found.append(
                    {
                        "role": role,
                        "label": label[:160],
                        "title": title[:160],
                        "description": description[:160],
                        "value": value[:160],
                        "bounds": {"x": round(x, 2), "y": round(y, 2), "width": round(width, 2), "height": round(height, 2)},
                        "center": {"x": round(x + width / 2, 2), "y": round(y + height / 2, 2)},
                    }
                )
                if len(found) >= limit:
                    return

        children = attr(element, AX.kAXChildrenAttribute)
        if children:
            for child in list(children):
                visit(child, depth + 1)
                if len(found) >= limit:
                    return

    visit(root)
    return {
        "ok": True,
        "tool": "ospilot_get_frontmost_ui_elements",
        "app": {"name": app.localizedName(), "pid": pid},
        "query": query,
        "count": len(found),
        "elements": found,
    }
