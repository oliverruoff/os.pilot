import asyncio
import json

from ospilot.pi.runtime import PiRuntime
from ospilot.core.paths import default_paths, ensure_paths


class FakeRpc:
    def __init__(self) -> None:
        self.calls = []
        self.starts = []
        self.stops = 0
        self.state = None

    async def call(self, method, params):
        self.calls.append((method, params))
        if method == "get_state" and self.state is not None:
            return self.state
        return {"ok": True}

    async def start(self, command, env):
        self.starts.append((command, env))

    async def stop(self):
        self.stops += 1


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
    assert "use at most one perception tool" in params["prompt"]
    assert "ospilot_get_frontmost_ui_elements" in params["prompt"]
    assert "ospilot_capture_screenshot_current_mouse_monitor returns an HD/720p JPEG" in params["prompt"]
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


def test_recent_sessions_uses_latest_user_titles_and_limits(tmp_path, monkeypatch) -> None:
    from ospilot.core.config import load_config

    home = tmp_path / "home"
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    paths = default_paths(home)
    ensure_paths(paths)
    config_file = tmp_path / "config.yaml"
    config_file.write_text("")
    for index in range(25):
        path = paths.pi_sessions / f"2026-06-08T17-{index:02d}-00-000Z_session-{index:02d}.jsonl"
        _write_jsonl(
            path,
            [
                {"type": "session", "id": f"session-{index:02d}"},
                {
                    "type": "message",
                    "message": {
                        "role": "user",
                        "content": [{"type": "text", "text": f"User request: title {index}"}],
                    },
                },
            ],
        )
        path.touch()

    sessions = PiRuntime(load_config(config_file), FakeRpc()).recent_sessions()

    assert len(sessions) == 20
    assert sessions[0].id == "session-24"
    assert sessions[0].title == "title 24"
    assert sessions[-1].id == "session-05"


def test_recent_sessions_prefers_metadata_title(tmp_path, monkeypatch) -> None:
    from ospilot.core.config import load_config

    home = tmp_path / "home"
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    paths = default_paths(home)
    ensure_paths(paths)
    config_file = tmp_path / "config.yaml"
    config_file.write_text("")
    _write_jsonl(
        paths.pi_sessions / "2026-06-08T17-00-00-000Z_abc.jsonl",
        [
            {"type": "session", "id": "abc", "title": "Named session"},
            {
                "type": "message",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "User request: ignored"}],
                },
            },
        ],
    )

    sessions = PiRuntime(load_config(config_file), FakeRpc()).recent_sessions()

    assert sessions[0].title == "Named session"


def test_recent_sessions_prefers_session_info_title(tmp_path, monkeypatch) -> None:
    from ospilot.core.config import load_config

    home = tmp_path / "home"
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    paths = default_paths(home)
    ensure_paths(paths)
    config_file = tmp_path / "config.yaml"
    config_file.write_text("")
    _write_jsonl(
        paths.pi_sessions / "2026-06-08T17-00-00-000Z_abc.jsonl",
        [
            {"type": "session", "id": "abc"},
            {
                "type": "message",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "User request: ignored"}],
                },
            },
            {"type": "session_info", "name": "Actual pi title"},
        ],
    )

    sessions = PiRuntime(load_config(config_file), FakeRpc()).recent_sessions()

    assert sessions[0].title == "Actual pi title"


def test_switch_session_restarts_pi_with_session_argument(tmp_path) -> None:
    from ospilot.core.config import load_config

    config_file = tmp_path / "config.yaml"
    config_file.write_text("pi:\n  executable: pi-test\n")
    rpc = FakeRpc()
    runtime = PiRuntime(load_config(config_file), rpc)  # type: ignore[arg-type]
    session_path = tmp_path / "session.jsonl"
    rpc.state = {"data": {"sessionFile": str(session_path)}}

    asyncio.run(runtime.switch_session(session_path, {"TOKEN": "secret"}))

    command, env = rpc.starts[0]
    assert rpc.stops == 1
    assert "--session" in command
    assert str(session_path) in command
    assert env["TOKEN"] == "secret"


def test_switch_session_fails_if_pi_loads_different_session(tmp_path) -> None:
    from ospilot.core.config import load_config

    config_file = tmp_path / "config.yaml"
    config_file.write_text("pi:\n  executable: pi-test\n")
    rpc = FakeRpc()
    runtime = PiRuntime(load_config(config_file), rpc)  # type: ignore[arg-type]
    session_path = tmp_path / "session.jsonl"
    rpc.state = {"data": {"sessionFile": str(tmp_path / "other.jsonl")}}

    try:
        asyncio.run(runtime.switch_session(session_path, {}))
    except RuntimeError as error:
        assert "instead of" in str(error)
    else:
        raise AssertionError("switch_session should fail on mismatched pi state")


def _write_jsonl(path, records) -> None:
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n")
