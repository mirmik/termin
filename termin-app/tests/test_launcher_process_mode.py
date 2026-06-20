import os

from termin.launcher import app as launcher_app


def _library_env_value(env):
    if os.name == "nt":
        return env.get("PATH", "")
    return env.get("LD_LIBRARY_PATH", "")


def test_launch_editor_process_spawn_mode(monkeypatch, tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    editor = bin_dir / "termin_editor"
    editor.write_text("", encoding="utf-8")
    project = str(tmp_path / "Project.terminproj")
    calls = []

    def fake_popen(args, env):
        calls.append((args, env))

    monkeypatch.setenv("TERMIN_LAUNCHER_MODE", "spawn")
    monkeypatch.setattr(launcher_app.subprocess, "Popen", fake_popen)

    assert launcher_app._launch_editor_process(str(editor), project) is True

    assert calls
    args, env = calls[0]
    assert args == [str(editor), project]
    assert str(tmp_path / "lib") in _library_env_value(env)


def test_launch_editor_process_exec_mode(monkeypatch, tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    editor = bin_dir / "termin_editor"
    editor.write_text("", encoding="utf-8")
    project = str(tmp_path / "Project.terminproj")
    calls = []
    spawn_calls = []

    def fake_execvpe(file, args, env):
        calls.append((file, args, env))

    def fake_popen(args, env):
        spawn_calls.append((args, env))

    monkeypatch.setenv("TERMIN_LAUNCHER_MODE", "exec")
    monkeypatch.setattr(launcher_app.os, "execvpe", fake_execvpe)
    monkeypatch.setattr(launcher_app.subprocess, "Popen", fake_popen)

    if os.name == "nt":
        assert launcher_app._launch_editor_process(str(editor), project) is True

        assert not calls
        assert spawn_calls
        args, env = spawn_calls[0]
        assert args == [str(editor), project]
        assert str(tmp_path / "lib") in _library_env_value(env)
        return

    assert launcher_app._launch_editor_process(str(editor), project) is False

    assert calls
    file, args, env = calls[0]
    assert file == str(editor)
    assert args == [str(editor), project]
    assert str(tmp_path / "lib") in _library_env_value(env)
