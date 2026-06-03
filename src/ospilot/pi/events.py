from __future__ import annotations

from dataclasses import dataclass
from typing import Any


KNOWN_EVENT_TYPES = {
    "agent_start",
    "turn_start",
    "message_start",
    "message_update",
    "message_end",
    "tool_execution_start",
    "tool_execution_update",
    "tool_execution_end",
    "agent_end",
    "extension_ui_request",
    "extension_error",
    "queue_update",
    "auto_retry_start",
    "auto_retry_end",
}


@dataclass(frozen=True)
class PiEvent:
    type: str
    payload: dict[str, Any]

    @classmethod
    def from_message(cls, message: dict[str, Any]) -> "PiEvent | None":
        event_type = message.get("event") or message.get("type")
        if not isinstance(event_type, str):
            return None
        if event_type == "response":
            return None
        payload = message.get("payload") if isinstance(message.get("payload"), dict) else message
        return cls(type=event_type, payload=payload)


def event_text(event: PiEvent) -> str:
    for key in ("text", "content", "message", "status"):
        value = event.payload.get(key)
        if isinstance(value, str):
            return value
    delta = event.payload.get("delta")
    if isinstance(delta, dict):
        value = delta.get("text") or delta.get("content")
        if isinstance(value, str):
            return value
    assistant_event = event.payload.get("assistantMessageEvent")
    if isinstance(assistant_event, dict):
        for key in ("text", "content", "delta"):
            value = assistant_event.get(key)
            if isinstance(value, str):
                return value
        content = assistant_event.get("content")
        if isinstance(content, dict) and isinstance(content.get("text"), str):
            return content["text"]
    message = event.payload.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            return "".join(parts)
    return ""
