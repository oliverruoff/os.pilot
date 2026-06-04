from __future__ import annotations

import asyncio
import shutil
import sys
import threading
from concurrent.futures import CancelledError
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from ospilot.config import load_config
from ospilot.ipc import IpcServer
from ospilot.logging import setup_logging
from ospilot.pi.events import event_text
from ospilot.pi.runtime import PiRuntime
from ospilot.tools.mouse import MouseController
from ospilot.tools.registry import build_default_registry
from ospilot.ui import CompanionBubble, CompanionState, CursorHalo, GlobalShortcuts, TrayController
from ospilot.ui.macos_window import configure_background_app


class UiDispatch(QObject):
    pi_event = Signal(str, str, str)
    error = Signal(str)
    ready = Signal(str)
    local_tool = Signal(str, str)
    companion_message = Signal(str)
    overlay_visibility = Signal(bool, object)


class OSPilotApp:
    def __init__(self) -> None:
        self.config = load_config()
        self.logger = setup_logging(self.config)
        self.qt = QApplication(sys.argv)
        configure_background_app()
        self.qt.setQuitOnLastWindowClosed(False)
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_forever, daemon=True).start()
        self.ui_dispatch = UiDispatch()
        self.ui_dispatch.pi_event.connect(self._apply_pi_event)
        self.ui_dispatch.error.connect(self._show_error)
        self.ui_dispatch.ready.connect(lambda message: self.tray.notify("OSPilot", message))
        self.ui_dispatch.local_tool.connect(self._apply_local_tool_state)
        self._stream_buffer = ""
        self._last_output = ""
        self._message_role = ""
        self._active_prompt = False
        self._watchdog = QTimer()
        self._watchdog.setSingleShot(True)
        self._watchdog.timeout.connect(self._handle_prompt_timeout)

        self.companion = CompanionBubble()
        self.ui_dispatch.companion_message.connect(self.companion.show_output)
        self.ui_dispatch.overlay_visibility.connect(self._apply_overlay_visibility)
        self.halo = CursorHalo()
        self.mouse = MouseController()
        self.registry = build_default_registry(self.config, self.mouse, self._emit_companion_message, self._emit_local_tool_state, self._set_screenshot_overlay_visibility)
        self.ipc = IpcServer(self.registry)
        self.runtime = PiRuntime(self.config)
        self.runtime.rpc.add_event_handler(self._on_pi_event)
        self.tray = TrayController(self.open_chat, self.open_voice, self.new_session, self.stop, self.quit)
        self.shortcuts = GlobalShortcuts(self.companion, self.open_chat, self.open_voice, self.stop)
        self.logger.info("shortcut backend=%s", self.shortcuts.backend)

    def run(self) -> int:
        self._install_extension()
        self.ipc.start()
        self.tray.show()
        self._schedule(self._start_runtime(), "start pi")
        return self.qt.exec()

    async def _start_runtime(self) -> None:
        await self.runtime.start({"OSPILOT_IPC_URL": self.ipc.url, "OSPILOT_IPC_TOKEN": self.ipc.token})
        state = await self.runtime.get_state()
        model = state.get("data", {}).get("model") if isinstance(state, dict) else None
        self.logger.info("pi started model=%s", model)
        if model:
            name = f"{model.get('provider')}/{model.get('id')}" if isinstance(model, dict) else str(model)
            self.ui_dispatch.ready.emit(f"pi ready: {name}")

    def open_chat(self) -> None:
        self.logger.info("open_chat")
        self.companion.show_chat(self.submit_prompt)

    def open_voice(self) -> None:
        self.logger.info("open_voice")
        self.companion.show_voice_placeholder()

    def submit_prompt(self, text: str) -> None:
        text = text.strip()
        self.logger.info("submit_prompt length=%s", len(text))
        if not text:
            return
        self.companion.input.clear()
        if text == "/new":
            self.new_session()
            return
        self.companion.show_status("Thinking...", CompanionState.THINKING)
        self._stream_buffer = ""
        self._last_output = ""
        self._message_role = ""
        self._active_prompt = True
        self._watchdog.start(45_000)
        self._schedule(self.runtime.prompt(text), "send prompt")

    def new_session(self) -> None:
        self.logger.info("new_session")
        self.companion.show_status("Starting new pi session...")
        self._schedule(self.runtime.new_session(), "new session")

    def stop(self) -> None:
        self.logger.info("stop")
        self._active_prompt = False
        self._watchdog.stop()
        self.mouse.stop()
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
        role = ""
        message = event.payload.get("message") if isinstance(event.payload, dict) else None
        if isinstance(message, dict) and isinstance(message.get("role"), str):
            role = message["role"]
        self.ui_dispatch.pi_event.emit(event.type, f"{role}\n{text}", tool_name or "")

    def _apply_pi_event(self, event_type: str, text: str, tool_name: str = "") -> None:
        role, text = self._split_event_text(text)
        if self._active_prompt:
            self._watchdog.start(45_000)
        if event_type in {"agent_start", "turn_start", "auto_retry_start"}:
            self.companion.show_status(text or "Thinking...", CompanionState.THINKING, tool_name)
        elif event_type == "message_start":
            self._message_role = role
            if role != "user":
                self._stream_buffer = ""
        elif event_type == "message_update" and text and self._message_role != "user":
            self._stream_buffer = self._merge_stream_text(self._stream_buffer, text)
            self._last_output = self._stream_buffer
            self.companion.show_output(self._stream_buffer)
        elif event_type == "message_end" and text and role != "user":
            if not self._stream_buffer or len(text) > len(self._stream_buffer):
                self._stream_buffer = text
            self._last_output = self._stream_buffer
            self.companion.show_output(self._stream_buffer)
        elif event_type == "tool_execution_start":
            self.companion.show_status(text or f"Running {tool_name}...", CompanionState.TOOL_RUNNING, tool_name)
        elif event_type == "tool_execution_update":
            self.companion.show_status(text or f"Running {tool_name}...", CompanionState.TOOL_RUNNING, tool_name)
        elif event_type == "tool_execution_end":
            if self._last_output:
                self.companion.show_output(self._last_output)
            else:
                self.companion.show_status(text or "Tool finished", CompanionState.TOOL_RUNNING, tool_name)
        elif event_type in {"agent_end", "auto_retry_end"}:
            self._active_prompt = False
            self._watchdog.stop()
            self.halo.hide_halo()
            if self._last_output:
                self.companion.show_final_output(self._last_output)
            else:
                self.companion.show_final_output(text or "Done.")
        elif event_type in {"extension_error"}:
            self._active_prompt = False
            self._watchdog.stop()
            self.companion.show_status(text or "Extension error", CompanionState.ERROR, tool_name)
            self.halo.show_halo("error")
        elif event_type == "extension_ui_request":
            self.companion.show_status(text or "pi requests input", CompanionState.EXTENSION_UI, tool_name)

    def _show_error(self, message: str) -> None:
        self._active_prompt = False
        self._watchdog.stop()
        self.halo.hide_halo()
        self.companion.show_status(message, CompanionState.ERROR)

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
            if visible:
                if self._active_prompt:
                    self.companion.show_status("Looking at your screen...", CompanionState.TOOL_RUNNING, "screenshot")
            else:
                self.halo.hide_halo()
                self.companion.hide()
        finally:
            done.set()

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
        self.halo.hide_halo()
        if self._last_output:
            self.companion.show_output(self._last_output)
        else:
            self.companion.show_status("No activity from pi for 45s. Use Stop and try again.", CompanionState.ERROR)

    def _split_event_text(self, value: str) -> tuple[str, str]:
        if "\n" not in value:
            return "", value
        role, text = value.split("\n", 1)
        return role, text

    def _merge_stream_text(self, current: str, incoming: str) -> str:
        if not current:
            return incoming
        if incoming.startswith(current):
            return incoming
        if current.endswith(incoming):
            return current
        return current + incoming

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

    def _install_extension(self) -> None:
        source = Path(__file__).resolve().parents[2] / "pi_extension" / "ospilot-desktop-tools.ts"
        target = self.config.paths.pi_extensions / "ospilot-desktop-tools.ts"
        if source.exists():
            shutil.copyfile(source, target)


def main() -> int:
    return OSPilotApp().run()


if __name__ == "__main__":
    raise SystemExit(main())
