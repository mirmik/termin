import sys
import types

import pytest

from termin.editor import run_editor


def test_init_editor_passes_engine_to_native_frontend(monkeypatch):
    engine = object()
    received = []
    session = object()
    frontend = types.ModuleType("termin.editor_native.run_editor")
    frontend.init_editor_native = lambda value, **kwargs: (
        received.append((value, kwargs)) or session
    )
    monkeypatch.setitem(sys.modules, "termin.editor_native.run_editor", frontend)
    monkeypatch.setattr(run_editor, "_parse_editor_args", lambda: (None, None, "native"))

    result = run_editor.init_editor(engine, debug_resource="albedo", no_scene=True)

    assert received == [(engine, {"debug_resource": "albedo", "no_scene": True})]
    assert result is session


def test_init_editor_returns_tcgui_frontend_session(monkeypatch):
    engine = object()
    session = object()
    frontend = types.ModuleType("termin.editor_tcgui.run_editor")
    frontend.init_editor_tcgui = lambda value, **kwargs: session if value is engine else None
    monkeypatch.setitem(sys.modules, "termin.editor_tcgui.run_editor", frontend)
    monkeypatch.setattr(run_editor, "_parse_editor_args", lambda: (None, None, "tcgui"))

    assert run_editor.init_editor(engine, no_scene=True) is session


def test_run_editor_runs_explicit_engine(monkeypatch):
    calls = []

    class _Session:
        def prepare_engine_shutdown(self):
            calls.append("prepare")

        def close(self):
            calls.append("close")

    class _Engine:
        def run(self):
            calls.append("run")

        def shutdown(self):
            calls.append("shutdown")
            return True

    engine = _Engine()
    monkeypatch.setattr(
        run_editor,
        "init_editor",
        lambda value, **kwargs: calls.append(value) or _Session(),
    )

    run_editor.run_editor(engine)

    assert calls == [engine, "run", "prepare", "shutdown", "close"]


def test_run_editor_finishes_all_shutdown_phases_after_prepare_failure(monkeypatch):
    calls = []

    class _Session:
        def prepare_engine_shutdown(self):
            calls.append("prepare")
            raise RuntimeError("prepare failed")

        def close(self):
            calls.append("close")

    class _Engine:
        def run(self):
            calls.append("run")

        def shutdown(self):
            calls.append("shutdown")
            return True

    engine = _Engine()
    monkeypatch.setattr(run_editor, "init_editor", lambda value, **kwargs: _Session())

    with pytest.raises(RuntimeError, match="prepare failed"):
        run_editor.run_editor(engine)

    assert calls == ["run", "prepare", "shutdown", "close"]


def test_init_editor_from_host_returns_session(monkeypatch):
    capsule = object()
    engine = object()
    session = object()

    engine_module = types.ModuleType("termin.engine")
    engine_module._borrow_engine_core = lambda value: engine if value is capsule else None
    monkeypatch.setitem(sys.modules, "termin.engine", engine_module)
    monkeypatch.setattr(run_editor, "init_editor", lambda value: session if value is engine else None)

    assert run_editor.init_editor_from_host(capsule) is session
