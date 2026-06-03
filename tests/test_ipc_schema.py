import json
import urllib.error
import urllib.request

from ospilot.ipc.server import IpcServer
from ospilot.tools.registry import ToolRegistry


def post(url: str, token: str, body: dict):
    request = urllib.request.Request(
        f"{url}/tool",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode())


def test_ipc_server_authenticates_and_dispatches_tool() -> None:
    registry = ToolRegistry()
    registry.register("demo", lambda payload: {"ok": True, "tool": "demo", "value": payload["value"]})
    server = IpcServer(registry, token="test-token")
    server.start()
    try:
        assert post(server.url, "test-token", {"tool": "demo", "payload": {"value": 42}})["value"] == 42
    finally:
        server.stop()


def test_ipc_server_rejects_bad_token() -> None:
    server = IpcServer(ToolRegistry(), token="test-token")
    server.start()
    try:
        try:
            post(server.url, "bad", {"tool": "demo"})
        except urllib.error.HTTPError as exc:
            assert exc.code == 401
        else:
            raise AssertionError("expected 401")
    finally:
        server.stop()
