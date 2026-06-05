from pathlib import Path

from ospilot.core.config import load_config, pi_environment


def test_load_config_merges_pi_args_from_env(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("pi:\n  executable: custom-pi\n  args: ['--foo']\n")
    monkeypatch.setenv("PI_ARGS", "--model kimi-coding/test")

    config = load_config(config_file)

    assert config.pi.executable == "custom-pi"
    assert config.pi.args == ["--foo", "--model", "kimi-coding/test"]


def test_pi_environment_sets_session_dir(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("")
    config = load_config(config_file)

    env = pi_environment(config, {"EXTRA": "1"})

    assert Path(env["PI_CODING_AGENT_SESSION_DIR"]).parts[-2:] == ("OSPilot", "pi-sessions")
    assert env["EXTRA"] == "1"


def test_windows_paths_use_appdata(tmp_path: Path, monkeypatch) -> None:
    from ospilot.core.paths import default_paths

    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))

    paths = default_paths(tmp_path / "home")

    assert paths.config_file == tmp_path / "roaming" / "OSPilot" / "config.yaml"
    assert paths.app_data == tmp_path / "local" / "OSPilot"
