from __future__ import annotations

import asyncio
import os
import sys
import threading
import time
from concurrent.futures import CancelledError

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from ospilot.core.config import load_config
from ospilot.core.logging import setup_logging
from ospilot.desktop import create_desktop_backend
from ospilot.desktop.registry import build_default_registry
from ospilot.ipc import IpcServer
from ospilot.pi.events import event_text, event_thinking_text, final_answer_text
from ospilot.pi.runtime import PiRuntime, PiSession, load_session_transcript
from ospilot.ui import CompanionBubble, CompanionState, CursorHalo, TrayController


class UiDispatch(QObject):
    pi_event = Signal(str, str, str, str)
    error = Signal(str)
    ready = Signal(str)
    local_tool = Signal(str, str)
    companion_message = Signal(str)
    overlay_visibility = Signal(bool, object)
    desktop_input_activity = Signal(str)


class OSPilotApp:
    def __init__(self) -> None:
        _configure_process_for_platform()
        self.config = load_config()
        self.logger = setup_logging(self.config)
        self.qt = QApplication(sys.argv)
        self.desktop = create_desktop_backend(self.config)
        self.desktop.configure_background_app()
        self.qt.setQuitOnLastWindowClosed(False)
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        self.ui_dispatch = UiDispatch()
        self.ui_dispatch.pi_event.connect(self._apply_pi_event)
        self.ui_dispatch.error.connect(self._show_error)
        self.ui_dispatch.ready.connect(lambda message: self.tray.notify("OSPilot", message))
        self.ui_dispatch.local_tool.connect(self._apply_local_tool_state)
        self._stream_buffer = ""
        self._thinking_buffer = ""
        self._last_output = ""
        self._last_final_output = ""
        self._message_role = ""
        self._conversation_history: list[tuple[str, str]] = []
        self._active_prompt = False
        self._keep_output_open_for_turn = False
        self._desktop_input_app_pid: int | None = None
        self._desktop_input_active = False
        self._watchdog = QTimer()
        self._watchdog.setSingleShot(True)
        self._watchdog.timeout.connect(self._handle_prompt_timeout)
        self._companion_visibility_timer = QTimer()
        self._companion_visibility_timer.timeout.connect(self._ensure_active_companion_visible)
        self._overlay_temporarily_hidden = False

        self.companion = CompanionBubble()
        self.ui_dispatch.companion_message.connect(self.companion.show_output)
        self.ui_dispatch.overlay_visibility.connect(self._apply_overlay_visibility)
        self.ui_dispatch.desktop_input_activity.connect(self._apply_desktop_input_activity)
        self.halo = CursorHalo()
        self._passive_companion_suppressed_until = 0.0
        self._pending_passive_companion: tuple[str, tuple, dict] | None = None
        self._passive_flush_timer = QTimer()
        self._passive_flush_timer.setSingleShot(True)
        self._passive_flush_timer.timeout.connect(self._flush_pending_passive_companion)
        self.registry = build_default_registry(
            self.config,
            self.desktop,
            self._emit_companion_message,
            self._emit_local_tool_state,
            self._set_screenshot_overlay_visibility,
            self._prepare_desktop_input,
            self._finish_desktop_input,
        )
        self.ipc = IpcServer(self.registry)
        self.runtime = PiRuntime(self.config)
        self.runtime.rpc.add_event_handler(self._on_pi_event)
        self._runtime_env_extra: dict[str, str] = {}
        self.tray = TrayController(
            self.open_chat,
            self.open_voice,
            self.new_session,
            self.list_sessions,
            self.switch_session,
            self.stop,
            self.quit,
        )
        self.shortcuts = self.desktop.create_global_shortcuts(self.companion, self.open_chat, self.open_voice, self.stop, self.show_last_answer)
        self.logger.info("shortcut backend=%s", self.shortcuts.backend)

    def run(self) -> int:
        self.ipc.start()
        self.tray.show()
        self._schedule(self._start_runtime(), "start pi")
        return self.qt.exec()

    async def _start_runtime(self) -> None:
        self._runtime_env_extra = {
            "OSPILOT_IPC_URL": self.ipc.url,
            "OSPILOT_IPC_TOKEN": self.ipc.token,
        }
        await self.runtime.start(self._runtime_env_extra)
        state = await self.runtime.get_state()
        model = state.get("data", {}).get("model") if isinstance(state, dict) else None
        self.logger.info("pi started model=%s", model)
        if model:
            name = f"{model.get('provider')}/{model.get('id')}" if isinstance(model, dict) else str(model)
            self.ui_dispatch.ready.emit(f"pi ready: {name}")

    def open_chat(self) -> None:
        self.logger.info("open_chat")
        self._remember_desktop_input_target()
        self.companion.show_chat(self.submit_prompt, self._conversation_history)

    def open_voice(self) -> None:
        self.logger.info("open_voice")
        self.companion.show_voice_placeholder()

    def submit_prompt(self, text: str) -> None:
        text = text.strip()
        self.logger.info("submit_prompt length=%s", len(text))
        if not text:
            return
        if self._desktop_input_app_pid is None:
            self._remember_desktop_input_target()
        self.companion.input.clear()
        if text == "/new":
            self.new_session()
            return
        self._conversation_history.append(("You", text))
        self.companion.begin_thinking()
        self._keep_output_open_for_turn = False
        self._stream_buffer = ""
        self._thinking_buffer = ""
        self._last_output = ""
        self._message_role = ""
        self._active_prompt = True
        self._watchdog.start(45_000)
        self._companion_visibility_timer.start(500)
        self._schedule(self.runtime.prompt(text), "send prompt")

    def new_session(self) -> None:
        self.logger.info("new_session")
        self._conversation_history.clear()
        message = "Starting new pi session..."
        self.companion.show_status(message)
        self.companion.start_countdown(message)
        self._schedule(self.runtime.new_session(), "new session")

    def list_sessions(self) -> list[PiSession]:
        return self.runtime.recent_sessions(20)

    def switch_session(self, session: PiSession) -> None:
        self.logger.info("switch_session id=%s path=%s", session.id, session.path)
        self._active_prompt = False
        self._watchdog.stop()
        self.desktop.stop()
        self.halo.hide_halo()
        self._conversation_history = load_session_transcript(session.path)
        message = f"Switching pi session: {session.title}"
        self.companion.show_status(message)
        self.companion.start_countdown(message)
        self._schedule(
            self.runtime.switch_session(session.path, self._runtime_env_extra),
            "switch session",
        )

    def show_last_answer(self) -> None:
        self.logger.info("show_last_answer")
        self._keep_output_open_for_turn = True
        self._pending_passive_companion = None
        self._passive_companion_suppressed_until = 0.0
        self._passive_flush_timer.stop()
        self.halo.hide_halo()
        text = self._last_final_output or final_answer_text(self._last_output) or self._thinking_buffer or self._stream_buffer
        if not text:
            return
        if self._conversation_history:
            self.companion.show_final_transcript(self._conversation_history, text)
        else:
            self.companion.show_output(text, expanded=False, fit_to_content=True)
        self.companion.cancel_countdown()

    def stop(self) -> None:
        self.logger.info("stop")
        self._active_prompt = False
        self._watchdog.stop()
        self._companion_visibility_timer.stop()
        self.desktop.stop()
        self.halo.hide_halo()
        self.companion.reset()
        self._schedule(self.runtime.abort(), "abort")

    def quit(self) -> None:
        self.ipc.stop()
        self._schedule(self.runtime.stop(), "stop pi")
        QTimer.singleShot(100, self.qt.quit)

    async def _on_pi_event(self, event) -> None:
        from ospilot.pi.events import tool_name_from_event
        tool_name = tool_name_from_event(event)
        self.logger.info("pi_event type=%s%s", event.type, f" tool={tool_name}" if tool_name else "")
        text = event_text(event)
        thinking_text = event_thinking_text(event)
        role = ""
        message = event.payload.get("message") if isinstance(event.payload, dict) else None
        if isinstance(message, dict) and isinstance(message.get("role"), str):
            role = message["role"]
        self.ui_dispatch.pi_event.emit(event.type, f"{role}\n{text}", tool_name or "", thinking_text)

    def _apply_pi_event(self, event_type: str, text: str, tool_name: str = "", thinking_text: str = "") -> None:
        role, text = self._split_event_text(text)
        if self._active_prompt:
            self._watchdog.start(45_000)
        if event_type in {"agent_start", "turn_start", "auto_retry_start"}:
            if thinking_text or text:
                self._show_passive_companion("show_stream", thinking_text or text)
        elif event_type == "message_start":
            self._message_role = role
            if role != "user":
                self._stream_buffer = ""
                self._thinking_buffer = ""
        elif event_type == "message_update" and self._message_role != "user":
            if thinking_text:
                self._thinking_buffer = self._merge_stream_text(self._thinking_buffer, thinking_text)
                self._show_passive_companion("show_stream", self._thinking_buffer)
            if text:
                self._stream_buffer = self._merge_stream_text(self._stream_buffer, text)
                self._last_output = self._stream_buffer
                if not thinking_text:
                    self._show_passive_companion("show_stream", self._stream_buffer)
        elif event_type == "message_end" and text and role != "user":
            self._stream_buffer = text
            self._last_output = self._stream_buffer
        elif event_type == "tool_execution_start":
            self._show_passive_companion("show_status", _tool_status_text(text, tool_name), CompanionState.TOOL_RUNNING, tool_name)
        elif event_type == "tool_execution_update":
            self._show_passive_companion("show_status", _tool_status_text(text, tool_name), CompanionState.TOOL_RUNNING, tool_name)
        elif event_type == "tool_execution_end":
            if self._last_output:
                self._show_passive_companion("show_stream", self._thinking_buffer or self._stream_buffer)
            else:
                self._show_passive_companion("show_status", _tool_status_text(text, tool_name, finished=True), CompanionState.TOOL_RUNNING, tool_name)
        elif event_type in {"agent_end", "auto_retry_end"}:
            self._active_prompt = False
            self._watchdog.stop()
            self._companion_visibility_timer.stop()
            self.halo.hide_halo()
            if self._last_output:
                final_text = final_answer_text(self._last_output)
            else:
                final_text = final_answer_text(text) or "Done."
            self._last_final_output = final_text
            self._conversation_history.append(("OSPilot", final_text))
            self._show_passive_companion("show_final_transcript", self._conversation_history, final_text, force=True)
            if self._keep_output_open_for_turn:
                self.companion.cancel_countdown()
        elif event_type in {"extension_error"}:
            self._active_prompt = False
            self._watchdog.stop()
            self._companion_visibility_timer.stop()
            self._show_passive_companion("show_status", text or "Extension error", CompanionState.ERROR, tool_name, force=True)
            self.halo.show_halo("error")
        elif event_type == "extension_ui_request":
            self._show_passive_companion("show_status", text or "pi requests input", CompanionState.EXTENSION_UI, tool_name)

    def _show_error(self, message: str) -> None:
        self._active_prompt = False
        self._watchdog.stop()
        self._companion_visibility_timer.stop()
        self.halo.hide_halo()
        self._show_passive_companion("show_status", message, CompanionState.ERROR)

    def _emit_local_tool_state(self, name: str, state: str) -> None:
        self.ui_dispatch.local_tool.emit(name, state)

    def _emit_companion_message(self, text: str) -> None:
        self.ui_dispatch.companion_message.emit(text)

    def _set_screenshot_overlay_visibility(self, visible: bool) -> None:
        done = threading.Event()
        self.ui_dispatch.overlay_visibility.emit(visible, done)
        done.wait(1.0)

    def _apply_overlay_visibility(self, visible: bool, done) -> None:
        try:
            self._overlay_temporarily_hidden = not visible
            if visible:
                if self._active_prompt:
                    text = self._thinking_buffer or self._stream_buffer or "Looking at your screen..."
                    self._show_passive_companion("show_stream", text)
            else:
                self.halo.show_halo("control", "Looking at your screen…")
                self.companion.hide()
        finally:
            done.set()

    def _ensure_active_companion_visible(self) -> None:
        if not self._active_prompt or self._overlay_temporarily_hidden:
            return
        self.companion.show_stream(self._thinking_buffer or self._stream_buffer or "Thinking...")

    def _show_passive_companion(self, method: str, *args, force: bool = False, **kwargs) -> None:
        if force:
            self._pending_passive_companion = None
            self._passive_companion_suppressed_until = 0.0
            self._passive_flush_timer.stop()
            self.halo.hide_halo()
            getattr(self.companion, method)(*args, **kwargs)
            return
        if time.monotonic() < self._passive_companion_suppressed_until:
            self._pending_passive_companion = (method, args, kwargs)
            self.halo.show_halo("control", self._passive_companion_summary(method, args))
            self._schedule_passive_companion_flush()
            return
        getattr(self.companion, method)(*args, **kwargs)

    def _passive_companion_summary(self, method: str, args: tuple) -> str:
        if method == "show_status" and args:
            return str(args[0]) or "Controlling UI…"
        if method == "show_stream" and args:
            return str(args[0]).strip().splitlines()[-1] or "Thinking…"
        if method == "show_final_transcript":
            return "Done."
        return "Controlling UI…"

    def _schedule_passive_companion_flush(self) -> None:
        remaining = self._passive_companion_suppressed_until - time.monotonic()
        delay_ms = max(50, int(remaining * 1000))
        self._passive_flush_timer.start(delay_ms)

    def _flush_pending_passive_companion(self) -> None:
        if time.monotonic() < self._passive_companion_suppressed_until:
            self._schedule_passive_companion_flush()
            return
        pending = self._pending_passive_companion
        self._pending_passive_companion = None
        if pending:
            method, args, kwargs = pending
            getattr(self.companion, method)(*args, **kwargs)
        if not self._active_prompt:
            self.halo.hide_halo()

    def _apply_desktop_input_activity(self, state: str) -> None:
        self._desktop_input_active = state == "start"
        if state == "start":
            self._pending_passive_companion = None
            self._passive_companion_suppressed_until = 0.0
            self._passive_flush_timer.stop()
            self.halo.show_halo("control", "Controlling UI…")
            if self._active_prompt:
                visible_text = self._thinking_buffer or self._stream_buffer
                if visible_text.strip():
                    self.companion.show_stream(visible_text)
                else:
                    self.companion.show_status("Controlling UI…", CompanionState.TOOL_RUNNING)
            return
        if not self._active_prompt:
            self.halo.hide_halo()

    def _remember_desktop_input_target(self) -> None:
        context = self.desktop.get_active_context()
        app = context.get("frontmost_app") if isinstance(context, dict) else None
        if not isinstance(app, dict):
            return
        pid = app.get("pid")
        if not isinstance(pid, int) or pid <= 0 or pid == os.getpid() or app.get("is_self"):
            return
        self._desktop_input_app_pid = pid
        self.logger.info("desktop input target app=%s pid=%s", app.get("name") or "", pid)

    def _prepare_desktop_input(self) -> None:
        self.ui_dispatch.desktop_input_activity.emit("start")
        if not self._desktop_input_app_pid:
            return
        result = self.desktop.focus_app(self._desktop_input_app_pid)
        if not result.get("ok"):
            self.logger.info("focus desktop input target failed: %s", result.get("error") or result)

    def _finish_desktop_input(self) -> None:
        self.ui_dispatch.desktop_input_activity.emit("end")

    def _apply_local_tool_state(self, name: str, state: str) -> None:
        if name == "ospilot_move_mouse":
            if state == "start":
                self.halo.show_halo("moving")
            else:
                self.halo.hide_halo()

    def _handle_prompt_timeout(self) -> None:
        if not self._active_prompt:
            return
        self._active_prompt = False
        self._companion_visibility_timer.stop()
        self.halo.hide_halo()
        if self._last_output:
            self.companion.show_output(final_answer_text(self._last_output))
        else:
            self.companion.show_status("No activity from pi for 45s. Use Stop and try again.", CompanionState.ERROR)

    def _split_event_text(self, value: str) -> tuple[str, str]:
        if "\n" not in value:
            return "", value
        role, text = value.split("\n", 1)
        return role, text

    def _merge_stream_text(self, current: str, incoming: str) -> str:
        return _merge_stream_text(current, incoming)

    def _schedule(self, coroutine, label: str) -> None:
        future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)
        future.add_done_callback(lambda f: self._handle_async_result(f, label))

    def _handle_async_result(self, future, label: str) -> None:
        try:
            error = future.exception()
        except CancelledError:
            return
        if not error:
            return
        error_message = str(error) or type(error).__name__
        self.logger.error("%s failed: %s", label, error_message)
        self.ui_dispatch.error.emit(f"{label} failed: {error_message}")


def main() -> int:
    return OSPilotApp().run()


def _merge_stream_text(current: str, incoming: str) -> str:
    if not current:
        return incoming
    if incoming.startswith(current):
        return incoming
    if current.endswith(incoming):
        return current
    max_overlap = min(len(current), len(incoming))
    for size in range(max_overlap, 0, -1):
        if current.endswith(incoming[:size]):
            return current + incoming[size:]
    return current + incoming


def _tool_status_text(text: str, tool_name: str = "", finished: bool = False) -> str:
    stripped = text.strip()
    if stripped and stripped not in {"{}", "[]", "null", "None"}:
        return stripped
    label = _tool_label(tool_name)
    if finished:
        return f"Finished {label}." if label else "Tool finished."
    return f"Running {label}..." if label else "Working..."


def _tool_label(tool_name: str) -> str:
    stripped = tool_name.strip()
    if not stripped:
        return ""
    return stripped.removeprefix("ospilot_").replace("_", " ")


def _configure_process_for_platform() -> None:
    if sys.platform == "win32":
        from ospilot.desktop.windows.window import set_process_dpi_awareness

        set_process_dpi_awareness()


if __name__ == "__main__":
    raise SystemExit(main())
