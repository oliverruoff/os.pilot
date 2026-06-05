from __future__ import annotations

import re
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
    if isinstance(delta, str):
        return delta
    if isinstance(delta, dict):
        value = delta.get("text") or delta.get("content") or delta.get("delta")
        if isinstance(value, str):
            return value
    assistant_event = event.payload.get("assistantMessageEvent")
    if isinstance(assistant_event, dict):
        for key in ("text", "content", "delta"):
            value = assistant_event.get(key)
            if isinstance(value, str):
                return value
        delta = assistant_event.get("delta")
        if isinstance(delta, dict):
            value = delta.get("text") or delta.get("content") or delta.get("delta")
            if isinstance(value, str):
                return value
        content = assistant_event.get("content")
        if isinstance(content, dict):
            return _content_item_text(content)
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and _is_final_text_part(item):
                    parts.append(_content_item_text(item))
            return "".join(parts)
    message = event.payload.get("message")
    if isinstance(message, dict):
        error = message.get("errorMessage")
        if isinstance(error, str):
            return error
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and _is_final_text_part(item):
                    parts.append(_content_item_text(item))
            return "".join(parts)
    return ""


def event_thinking_text(event: PiEvent) -> str:
    for key in ("thinking", "reasoning", "thought"):
        value = event.payload.get(key)
        if isinstance(value, str):
            return value
    delta = event.payload.get("delta")
    if isinstance(delta, dict):
        for key in ("thinking", "reasoning", "thought"):
            value = delta.get(key)
            if isinstance(value, str):
                return value
    assistant_event = event.payload.get("assistantMessageEvent")
    if isinstance(assistant_event, dict):
        text = _thinking_text_from_container(assistant_event)
        if text:
            return text
    message = event.payload.get("message")
    if isinstance(message, dict):
        return _thinking_text_from_container(message)
    return ""


def final_answer_text(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    marker_match = re.search(r"(?is)(?:^|\n|\b)(?:final\s+answer|answer)\s*:\s*(.+)$", stripped)
    if marker_match:
        return marker_match.group(1).strip()
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", stripped) if part.strip()]
    if len(paragraphs) > 1 and _looks_like_reasoning(paragraphs[-2]):
        return paragraphs[-1]
    sentences = re.findall(r".+?(?:[.!?](?=\s|$)|$)", stripped, flags=re.S)
    sentences = [sentence.strip() for sentence in sentences if sentence.strip()]
    if len(sentences) > 1 and _looks_like_reasoning(" ".join(sentences[:-1])):
        return sentences[-1]
    return stripped


def _is_final_text_part(item: dict[str, Any]) -> bool:
    for key in ("type", "name", "kind"):
        value = item.get(key)
        if not isinstance(value, str):
            continue
        normalized = value.lower()
        if any(marker in normalized for marker in ("reasoning", "thinking", "thought")):
            return False
    return True


def _content_item_text(item: dict[str, Any]) -> str:
    for key in ("text", "content", "delta"):
        value = item.get(key)
        if isinstance(value, str):
            return value
    delta = item.get("delta")
    if isinstance(delta, dict):
        for key in ("text", "content", "delta"):
            value = delta.get(key)
            if isinstance(value, str):
                return value
    return ""


def _looks_like_reasoning(text: str) -> bool:
    normalized = text.lower()
    markers = (
        "the user said",
        "user said",
        "i should",
        "i probably",
        "i need",
        "i can",
        "i'll",
        "let me",
    )
    return any(marker in normalized for marker in markers)


def _thinking_text_from_container(container: dict[str, Any]) -> str:
    for key in ("thinking", "reasoning", "thought"):
        value = container.get(key)
        if isinstance(value, str):
            return value
    content = container.get("content")
    if isinstance(content, dict) and _is_thinking_text_part(content) and isinstance(content.get("text"), str):
        return content["text"]
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and _is_thinking_text_part(item) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return ""


def _is_thinking_text_part(item: dict[str, Any]) -> bool:
    for key in ("type", "name", "kind"):
        value = item.get(key)
        if not isinstance(value, str):
            continue
        normalized = value.lower()
        if any(marker in normalized for marker in ("reasoning", "thinking", "thought")):
            return True
    return False


def tool_name_from_event(event: PiEvent) -> str | None:
    if event.type in ("tool_execution_start", "tool_execution_update", "tool_execution_end"):
        name = event.payload.get("toolName")
        if isinstance(name, str):
            return name
    return None
