from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from ospilot.desktop.registry import ToolRegistry

from .auth import make_token
from .schemas import validate_tool_request


class IpcServer:
    def __init__(self, registry: ToolRegistry, token: str | None = None) -> None:
        self.registry = registry
        self.token = token or make_token()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._executor = ThreadPoolExecutor(max_workers=4)

    @property
    def port(self) -> int:
        if not self._server:
            raise RuntimeError("IPC server is not running")
        return int(self._server.server_address[1])

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        if self._server:
            return
        registry = self.registry
        token = self.token

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802
                if self.path != "/tool":
                    self._send(404, {"ok": False, "error": "not found"})
                    return
                if self.headers.get("Authorization") != f"Bearer {token}":
                    self._send(401, {"ok": False, "error": "unauthorized"})
                    return
                length = int(self.headers.get("Content-Length", "0"))
                try:
                    body = json.loads(self.rfile.read(length).decode() or "{}")
                    tool, payload = validate_tool_request(body)
                    future = self.server.executor.submit(registry.call, tool, payload)
                    try:
                        self._send(200, future.result(timeout=55))
                    except TimeoutError:
                        self._send(504, {"ok": False, "tool": tool, "error": "tool timed out"})
                except Exception as exc:
                    self._send(400, {"ok": False, "error": str(exc)})

            def log_message(self, format: str, *args: Any) -> None:
                return

            def _send(self, status: int, body: dict[str, Any]) -> None:
                payload = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.executor = self._executor  # type: ignore[attr-defined]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        self._executor.shutdown(wait=False, cancel_futures=True)
