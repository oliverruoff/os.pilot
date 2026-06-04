from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .events import PiEvent


EventHandler = Callable[[PiEvent], Awaitable[None] | None]

# Screenshot tool results can include base64 image content. pi RPC is newline-delimited
# JSON, so a single event line may be several MB; the asyncio default reader
# limit (64 KiB) is too small and makes stdout reading stop mid-turn.
RPC_STREAM_LIMIT = 64 * 1024 * 1024


@dataclass(frozen=True)
class JsonRpcMessage:
    jsonrpc: str = "2.0"
    id: int | None = None
    method: str | None = None
    params: dict[str, Any] | None = None
    result: Any = None
    error: Any = None

    def to_json(self) -> str:
        data: dict[str, Any] = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            data["id"] = self.id
        if self.method is not None:
            data["method"] = self.method
        if self.params is not None:
            data["params"] = self.params
        if self.result is not None:
            data["result"] = self.result
        if self.error is not None:
            data["error"] = self.error
        return json.dumps(data, separators=(",", ":"))


@dataclass(frozen=True)
class PiRpcCommand:
    type: str
    id: int | None = None
    message: str | None = None
    response: str | None = None
    request_id: str | None = None

    def to_json(self) -> str:
        data: dict[str, Any] = {"type": self.type}
        if self.id is not None:
            data["id"] = self.id
        if self.message is not None:
            data["message"] = self.message
        if self.response is not None:
            data["response"] = self.response
        if self.request_id is not None:
            data["request_id"] = self.request_id
        return json.dumps(data, separators=(",", ":"))


class PiRpcClient:
    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._next_id = 1
        self._pending: dict[str, asyncio.Future[Any]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._handlers: list[EventHandler] = []
        self._logger = logger or logging.getLogger("ospilot.pi.rpc")

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    def add_event_handler(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    async def start(self, command: list[str], env: dict[str, str]) -> None:
        if self.is_running:
            return
        self._process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            limit=RPC_STREAM_LIMIT,
        )
        self._reader_task = asyncio.create_task(self._read_stdout())
        asyncio.create_task(self._read_stderr())
        await asyncio.sleep(0)
        if self._process.returncode is not None:
            raise RuntimeError(f"pi RPC process exited with code {self._process.returncode}")

    async def stop(self) -> None:
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()
        if self._reader_task:
            self._reader_task.cancel()
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=2)
            except asyncio.TimeoutError:
                self._process.kill()
                await self._process.wait()
        self._process = None

    async def call(self, method: str, params: dict[str, Any] | None = None, timeout: float = 30) -> Any:
        if not self.is_running or not self._process or not self._process.stdin:
            raise RuntimeError("pi RPC process is not running")
        numeric_id = self._next_id
        self._next_id += 1
        request_id = str(numeric_id)
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        self._pending[request_id] = future
        self._process.stdin.write((self._encode_command(method, params or {}, numeric_id) + "\n").encode())
        await self._process.stdin.drain()
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending.pop(request_id, None)

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        if not self.is_running or not self._process or not self._process.stdin:
            raise RuntimeError("pi RPC process is not running")
        numeric_id = self._next_id
        self._next_id += 1
        self._process.stdin.write((self._encode_command(method, params or {}, numeric_id) + "\n").encode())
        await self._process.stdin.drain()

    def _encode_command(self, method: str, params: dict[str, Any], request_id: int) -> str:
        if method == "prompt":
            return PiRpcCommand(type="prompt", id=request_id, message=str(params.get("prompt") or params.get("message") or "")).to_json()
        if method == "extension_ui_response":
            return json.dumps({"type": "extension_ui_response", "id": str(params.get("request_id", "")), "response": str(params.get("response", ""))}, separators=(",", ":"))
        return PiRpcCommand(type=method, id=request_id).to_json()

    async def _read_stdout(self) -> None:
        assert self._process and self._process.stdout
        try:
            while line := await self._process.stdout.readline():
                try:
                    message = json.loads(line.decode())
                except json.JSONDecodeError:
                    self._logger.warning("invalid pi rpc line")
                    continue
                await self.route_message(message)
        except Exception:
            self._logger.exception("pi stdout reader failed")
        finally:
            self._logger.warning("pi stdout reader exited")
            for future in list(self._pending.values()):
                if not future.done():
                    future.set_exception(RuntimeError("pi process closed stdout"))
            self._pending.clear()

    async def _read_stderr(self) -> None:
        assert self._process and self._process.stderr
        try:
            while line := await self._process.stderr.readline():
                self._logger.info("pi stderr: %s", line.decode(errors="replace").strip())
        finally:
            self._logger.warning("pi stderr reader exited")

    async def route_message(self, message: dict[str, Any]) -> None:
        if message.get("type") == "response":
            request_id = message.get("id")
            if not isinstance(request_id, int):
                return
            future = self._pending.get(str(request_id))
            if not future:
                return
            if future.done():
                return
            if not message.get("success", False):
                future.set_exception(RuntimeError(str(message.get("error", "pi command failed"))))
            else:
                future.set_result(message)
            return

        event = PiEvent.from_message(message)
        if not event:
            return
        for handler in list(self._handlers):
            result = handler(event)
            if asyncio.iscoroutine(result):
                await result
