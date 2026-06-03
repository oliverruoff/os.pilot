import asyncio

from ospilot.pi.runtime import PiRuntime
from ospilot.paths import default_paths, ensure_paths


class FakeRpc:
    def __init__(self) -> None:
        self.calls = []

    async def call(self, method, params):
        self.calls.append((method, params))
        return {"ok": True}


def test_new_session_calls_pi_method(tmp_path) -> None:
    from ospilot.config import load_config

    config_file = tmp_path / "config.yaml"
    config_file.write_text("")
    rpc = FakeRpc()
    runtime = PiRuntime(load_config(config_file), rpc)  # type: ignore[arg-type]

    asyncio.run(runtime.new_session())

    assert rpc.calls == [("new_session", {})]


def test_runtime_command_uses_extension_not_skill(tmp_path, monkeypatch) -> None:
    from ospilot.config import load_config

    home = tmp_path / "home"
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    paths = default_paths(home)
    ensure_paths(paths)
    (paths.pi_extensions / "ospilot-desktop-tools.ts").write_text("export default function () {}")

    config_file = tmp_path / "config.yaml"
    config_file.write_text("pi:\n  executable: pi-test\n")
    runtime = PiRuntime(load_config(config_file), FakeRpc())  # type: ignore[arg-type]

    command = runtime.command()

    assert command[:2] == ["pi-test", "--mode"]
    assert "--extension" in command
    assert "--skill" not in command
