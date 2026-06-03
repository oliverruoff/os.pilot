from __future__ import annotations

from typing import Any


def validate_tool_request(data: Any) -> tuple[str, dict[str, Any]]:
    if not isinstance(data, dict):
        raise ValueError("request body must be an object")
    tool = data.get("tool")
    payload = data.get("payload", {})
    if not isinstance(tool, str) or not tool:
        raise ValueError("tool must be a non-empty string")
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    return tool, payload
