from __future__ import annotations

from typing import Any

from ospilot.core.config import AppConfig, pi_environment

from .rpc import PiRpcClient


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


class PiRuntime:
    def __init__(self, config: AppConfig, rpc: PiRpcClient | None = None) -> None:
        self.config = config
        self.rpc = rpc or PiRpcClient()

    def command(self) -> list[str]:
        command = [self.config.pi.executable, "--mode", "rpc", "--session-dir", str(self.config.paths.pi_sessions)]
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
        return await self.rpc.call("new_session", {})

    async def get_state(self) -> Any:
        return await self.rpc.call("get_state", {})

    async def extension_ui_response(self, request_id: str, response: str) -> Any:
        return await self.rpc.call("extension_ui_response", {"request_id": request_id, "response": response})
