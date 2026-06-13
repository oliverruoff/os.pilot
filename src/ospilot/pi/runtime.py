from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ospilot.core.config import AppConfig, pi_environment

from .rpc import PiRpcClient


@dataclass(frozen=True)
class PiSession:
    id: str
    title: str
    path: Path


OSPILOT_FAST_TOOL_HINT = """OSPilot visual-grounding hint:
- When the user asks where a named UI control/setting/button is, or asks to click one, first call ospilot_get_frontmost_ui_elements with a short query. Use the returned exact center coordinates for ospilot_move_mouse or ospilot_click with coordinate_space="display_point"; this is faster and more precise than visual guessing.
- Only call ospilot_capture_screenshot_current_mouse_monitor when Accessibility cannot identify the target or the target is purely visual. Inspect screenshot metadata, especially mouse_position, monitor_bounds, screenshot_size, and scale_factor.
- After locating the requested item, choose the exact center of the relevant UI element/icon/label and call ospilot_move_mouse. For screenshot-based targets, prefer normalized coordinates relative to the screenshot/monitor; if using exact screenshot pixel coordinates from the latest screenshot, set coordinate_space="screenshot_pixel".
- Do not click for \"where is ...\" / \"show me ...\" requests unless the user explicitly asks to click or open it.
"""

OSPILOT_FINAL_RESPONSE_HINT = """OSPilot final-response hint:
- Final responses must contain only the user-facing answer or outcome.
- Do not include planning, self-talk, reasoning summaries, or phrases like "I need to", "I should", or "let me".
"""


def load_session_transcript(path: Path, limit: int = 40) -> list[tuple[str, str]]:
    messages: list[tuple[str, str]] = []
    try:
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                item = _transcript_message(record)
                if item:
                    messages.append(item)
    except OSError:
        return []
    return messages[-limit:]


class PiRuntime:
    def __init__(self, config: AppConfig, rpc: PiRpcClient | None = None) -> None:
        self.config = config
        self.rpc = rpc or PiRpcClient()
        self._session_path: Path | None = None

    def command(self) -> list[str]:
        command = [self.config.pi.executable, "--mode", "rpc", "--session-dir", str(self.config.paths.pi_sessions)]
        if self._session_path:
            command.extend(["--session", str(self._session_path)])
        extension = self.config.paths.pi_desktop_tools_extension
        if extension.exists():
            command.extend(["--extension", str(extension)])
        skills = self.config.paths.pi_skills_source
        if skills.exists():
            command.extend(["--skill", str(skills)])
        command.extend(self.config.pi.args)
        return command

    async def start(self, env_extra: dict[str, str] | None = None) -> None:
        await self.rpc.start(self.command(), pi_environment(self.config, env_extra))

    async def switch_session(self, session_path: Path, env_extra: dict[str, str] | None = None) -> None:
        self._session_path = session_path
        await self.stop()
        await self.start(env_extra)
        state = await self.get_state()
        if not _state_matches_session(state, session_path):
            loaded = _state_session_description(state)
            raise RuntimeError(f"pi loaded {loaded} instead of {session_path}")

    async def stop(self) -> None:
        await self.rpc.stop()

    async def prompt(self, text: str, context: dict[str, Any] | None = None) -> Any:
        return await self.rpc.call("prompt", {"prompt": self._with_fast_tool_hint(text), "context": context or {}})

    def _with_fast_tool_hint(self, text: str) -> str:
        return f"{OSPILOT_FAST_TOOL_HINT}\n{OSPILOT_FINAL_RESPONSE_HINT}\nUser request: {text}"

    async def abort(self) -> Any:
        await self.rpc.notify("abort", {})
        return {"ok": True}

    async def new_session(self) -> Any:
        self._session_path = None
        return await self.rpc.call("new_session", {})

    async def get_state(self) -> Any:
        return await self.rpc.call("get_state", {})

    async def extension_ui_response(self, request_id: str, response: str) -> Any:
        return await self.rpc.call("extension_ui_response", {"request_id": request_id, "response": response})

    def recent_sessions(self, limit: int = 20) -> list[PiSession]:
        session_dir = self.config.paths.pi_sessions
        if not session_dir.exists():
            return []
        files = sorted(
            session_dir.glob("*.jsonl"),
            key=lambda path: (path.stat().st_mtime, path.name),
            reverse=True,
        )
        sessions: list[PiSession] = []
        for path in files:
            session = _read_session(path)
            if not session:
                continue
            sessions.append(session)
            if len(sessions) >= limit:
                break
        return sessions


def _read_session(path: Path) -> PiSession | None:
    session_id = ""
    title = ""
    title_is_metadata = False
    record_count = 0
    try:
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                record_count += 1
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(record, dict):
                    continue
                if record.get("type") == "session":
                    session_id = str(record.get("id") or "")
                    title = _metadata_title(record)
                    title_is_metadata = bool(title)
                if record.get("type") == "session_info":
                    title = _metadata_title(record) or title
                    title_is_metadata = bool(title)
                if not title and record.get("type") == "message":
                    title = _message_title(record)
                if session_id and title and (title_is_metadata or record_count >= 20):
                    break
    except OSError:
        return None
    session_id = session_id or _session_id_from_filename(path)
    title = title or session_id or path.stem
    return PiSession(id=session_id, title=_shorten_title(title), path=path)


def _metadata_title(record: dict[str, Any]) -> str:
    for key in ("title", "name", "displayName", "display_name"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _transcript_message(record: dict[str, Any]) -> tuple[str, str] | None:
    if record.get("type") != "message":
        return None
    message = record.get("message")
    if not isinstance(message, dict):
        return None
    role = message.get("role")
    if role == "user":
        text = _message_content_text(message, include_thinking=False)
        text = _strip_prompt_prefix(text).strip()
        return ("You", _shorten_transcript_text(text)) if text else None
    if role == "assistant":
        text = _message_content_text(message, include_thinking=False).strip()
        return ("OSPilot", _shorten_transcript_text(text)) if text else None
    return None


def _message_content_text(message: dict[str, Any], include_thinking: bool = False) -> str:
    content = message.get("content")
    parts = content if isinstance(content, list) else [content]
    texts: list[str] = []
    for part in parts:
        if isinstance(part, str):
            texts.append(part)
        elif isinstance(part, dict):
            part_type = str(part.get("type") or "")
            if part_type in {"toolCall", "toolResult"}:
                continue
            if not include_thinking and part_type in {"thinking", "reasoning", "thought"}:
                continue
            value = part.get("text")
            if isinstance(value, str):
                texts.append(value)
    return "\n".join(text.strip() for text in texts if text and text.strip())


def _shorten_transcript_text(text: str, limit: int = 1200) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _message_title(record: dict[str, Any]) -> str:
    message = record.get("message")
    if not isinstance(message, dict) or message.get("role") != "user":
        return ""
    return _strip_prompt_prefix(_message_content_text(message, include_thinking=False)).strip()


def _strip_prompt_prefix(text: str) -> str:
    marker = "User request:"
    if marker in text:
        return text.rsplit(marker, 1)[1]
    return text


def _session_id_from_filename(path: Path) -> str:
    stem = path.stem
    if "_" in stem:
        return stem.rsplit("_", 1)[1]
    return stem


def _shorten_title(title: str, limit: int = 80) -> str:
    collapsed = " ".join(title.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3].rstrip() + "..."


def _state_matches_session(state: Any, session_path: Path) -> bool:
    data = state.get("data") if isinstance(state, dict) else None
    if not isinstance(data, dict):
        return False
    session_file = data.get("sessionFile")
    if isinstance(session_file, str):
        try:
            if Path(session_file).resolve() == session_path.resolve():
                return True
        except OSError:
            if session_file == str(session_path):
                return True
    session_id = data.get("sessionId")
    return isinstance(session_id, str) and session_id == _session_id_from_filename(session_path)


def _state_session_description(state: Any) -> str:
    data = state.get("data") if isinstance(state, dict) else None
    if not isinstance(data, dict):
        return "an unknown session"
    session_file = data.get("sessionFile")
    session_id = data.get("sessionId")
    if session_file:
        return str(session_file)
    if session_id:
        return f"session {session_id}"
    return "an unknown session"
