from __future__ import annotations

from typing import Any

from ospilot.config import AppConfig, pi_environment

from .rpc import PiRpcClient


class PiRuntime:
    def __init__(self, config: AppConfig, rpc: PiRpcClient | None = None) -> None:
        self.config = config
        self.rpc = rpc or PiRpcClient()

    def command(self) -> list[str]:
        command = [self.config.pi.executable, "--mode", "rpc", "--session-dir", str(self.config.paths.pi_sessions)]
        extension = self.config.paths.pi_extensions / "ospilot-desktop-tools.ts"
        if extension.exists():
            command.extend(["--extension", str(extension)])
        command.extend(self.config.pi.args)
        return command

    async def start(self, env_extra: dict[str, str] | None = None) -> None:
        await self.rpc.start(self.command(), pi_environment(self.config, env_extra))

    async def stop(self) -> None:
        await self.rpc.stop()

    async def prompt(self, text: str, context: dict[str, Any] | None = None) -> Any:
        return await self.rpc.call("prompt", {"prompt": text, "context": context or {}})

    async def abort(self) -> Any:
        await self.rpc.notify("abort", {})
        return {"ok": True}

    async def new_session(self) -> Any:
        return await self.rpc.call("new_session", {})

    async def get_state(self) -> Any:
        return await self.rpc.call("get_state", {})

    async def extension_ui_response(self, request_id: str, response: str) -> Any:
        return await self.rpc.call("extension_ui_response", {"request_id": request_id, "response": response})
