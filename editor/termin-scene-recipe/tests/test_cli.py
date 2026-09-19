import contextlib
import io
import json
from types import SimpleNamespace

import pytest

from termin.scene_recipe import cli


def _arguments(tmp_path, action="plan", *extra):
    recipe = tmp_path / "recipe.json"
    recipe.write_text('{"namespace":"example","placements":[]}')
    return [action, str(recipe), "--session", str(tmp_path / "session.json"),
            "--project", str(tmp_path / "project" / "Game.terminproj"), *extra]


def _editor(monkeypatch, project, service):
    monkeypatch.setattr(cli, "load_session", lambda path: {"token": "secret"})

    def call(session, method, params):
        assert method == "tools/call"
        assert params["name"] == "execute_python_script"
        output = io.StringIO()
        error = None
        try:
            with contextlib.redirect_stdout(output):
                exec(params["arguments"]["script"], {
                    "project_path": str(project), "scene_recipe": service,
                })
        except Exception as exc:
            error = str(exc)
        return {"result": {
            "isError": error is not None,
            "structuredContent": {"ok": error is None, "output": output.getvalue(), "error": error},
        }}

    monkeypatch.setattr(cli, "call", call)


def test_plan_uses_installed_service_and_normalizes_project_file(tmp_path, monkeypatch, capsys):
    calls = []

    def run(*args):
        calls.append(args)
        print("Incidental engine log")
        return {"conflicts": [], "placements": []}

    _editor(monkeypatch, tmp_path / "project", SimpleNamespace(run=run))
    assert cli.main(_arguments(tmp_path)) == 0
    assert calls == [("plan", {"namespace": "example", "placements": []}, None, None, None)]
    assert json.loads(capsys.readouterr().out) == {"conflicts": [], "placements": []}


def test_wrong_project_stops_before_service_call(tmp_path, monkeypatch, capsys):
    calls = []
    _editor(monkeypatch, tmp_path / "another-project", SimpleNamespace(run=lambda *args: calls.append(args)))
    assert cli.main(_arguments(tmp_path, "sync")) == 1
    assert calls == []
    assert "Wrong editor project" in json.loads(capsys.readouterr().err)["error"]


def test_conflicts_are_json_with_nonzero_exit(tmp_path, monkeypatch, capsys):
    result = {"conflicts": [{"id": "one"}], "applied": False}
    _editor(monkeypatch, tmp_path / "project", SimpleNamespace(run=lambda *args: result))
    assert cli.main(_arguments(tmp_path, "sync")) == 1
    assert json.loads(capsys.readouterr().out) == result


def test_list_ids_are_not_interpreted_as_errors(tmp_path, monkeypatch, capsys):
    result = {"conflicts": {"uuid": "one"}, "error": {"uuid": "two"}}
    _editor(monkeypatch, tmp_path / "project", SimpleNamespace(run=lambda *args: result))
    assert cli.main(_arguments(tmp_path, "list")) == 0
    assert json.loads(capsys.readouterr().out) == result


def test_error_redacts_session_token(tmp_path, monkeypatch, capsys):
    def run(*args):
        raise RuntimeError("Bearer secret")

    _editor(monkeypatch, tmp_path / "project", SimpleNamespace(run=run))
    assert cli.main(_arguments(tmp_path)) == 1
    assert "secret" not in capsys.readouterr().err


@pytest.mark.parametrize("extra", [[], ["--session", "session.json"], ["--project", "project"]])
def test_explicit_session_and_project_are_required(extra):
    with pytest.raises(SystemExit) as error:
        cli.main(["plan", "recipe.json", *extra])
    assert error.value.code == 2


@pytest.mark.parametrize("action, extra", [
    ("replace", []), ("reset-transform", []), ("plan", ["--resolutions", "resolutions.json"]),
])
def test_incomplete_mutation_arguments_are_rejected(tmp_path, action, extra):
    with pytest.raises(SystemExit) as error:
        cli.main(_arguments(tmp_path, action, *extra))
    assert error.value.code == 2
