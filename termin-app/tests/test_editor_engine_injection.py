import sys
import types

from termin.editor import run_editor


def test_init_editor_passes_engine_to_native_frontend(monkeypatch):
    engine = object()
    received = []
    frontend = types.ModuleType("termin.editor_native.run_editor")
    frontend.init_editor_native = lambda value, **kwargs: received.append((value, kwargs))
    monkeypatch.setitem(sys.modules, "termin.editor_native.run_editor", frontend)
    monkeypatch.setattr(run_editor, "_parse_editor_args", lambda: (None, None, "native"))

    run_editor.init_editor(engine, debug_resource="albedo", no_scene=True)

    assert received == [(engine, {"debug_resource": "albedo", "no_scene": True})]


def test_run_editor_runs_explicit_engine(monkeypatch):
    calls = []

    class _Engine:
        def run(self):
            calls.append("run")

    engine = _Engine()
    monkeypatch.setattr(run_editor, "init_editor", lambda value, **kwargs: calls.append(value))

    run_editor.run_editor(engine)

    assert calls == [engine, "run"]
