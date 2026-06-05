import asyncio

from ospilot.pi.runtime import PiRuntime
from ospilot.core.paths import default_paths, ensure_paths


class FakeRpc:
    def __init__(self) -> None:
        self.calls = []

    async def call(self, method, params):
        self.calls.append((method, params))
        return {"ok": True}


def test_new_session_calls_pi_method(tmp_path) -> None:
    from ospilot.core.config import load_config

    config_file = tmp_path / "config.yaml"
    config_file.write_text("")
    rpc = FakeRpc()
    runtime = PiRuntime(load_config(config_file), rpc)  # type: ignore[arg-type]

    asyncio.run(runtime.new_session())

    assert rpc.calls == [("new_session", {})]


def test_prompt_includes_visual_pointing_tool_hint(tmp_path) -> None:
    from ospilot.core.config import load_config

    config_file = tmp_path / "config.yaml"
    config_file.write_text("")
    rpc = FakeRpc()
    runtime = PiRuntime(load_config(config_file), rpc)  # type: ignore[arg-type]

    asyncio.run(runtime.prompt("where is the search button?"))

    method, params = rpc.calls[0]
    assert method == "prompt"
    assert "first call ospilot_get_frontmost_ui_elements" in params["prompt"]
    assert "Only call ospilot_capture_screenshot_current_mouse_monitor" in params["prompt"]
    assert "mouse_position" in params["prompt"]
    assert "User request: where is the search button?" in params["prompt"]


def test_runtime_command_uses_extension_and_referenced_skills(tmp_path, monkeypatch) -> None:
    from ospilot.core.config import load_config

    home = tmp_path / "home"
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    paths = default_paths(home)
    ensure_paths(paths)
    config_file = tmp_path / "config.yaml"
    config_file.write_text("pi:\n  executable: pi-test\n")
    runtime = PiRuntime(load_config(config_file), FakeRpc())  # type: ignore[arg-type]

    command = runtime.command()

    assert command[:2] == ["pi-test", "--mode"]
    assert "--extension" in command
    assert str(paths.pi_desktop_tools_extension) in command
    assert "--skill" in command
    assert str(paths.pi_skills_source) in command
