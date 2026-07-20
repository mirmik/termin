import gc
import weakref

import pytest

from termin.engine import EngineCore, EngineLoopClient


def test_python_engine_requires_an_attached_loop_client() -> None:
    engine = EngineCore()

    with pytest.raises(RuntimeError, match="requires an attached loop client"):
        engine.run()

    assert not engine.is_running()


def test_python_loop_client_attaches_runs_and_detaches_atomically() -> None:
    engine = EngineCore()
    engine.target_fps = 0.0
    calls = {"poll": 0, "continue": 0, "shutdown": 0}

    client = EngineLoopClient(
        poll_events=lambda: calls.__setitem__("poll", calls["poll"] + 1),
        should_continue=lambda: (
            calls.__setitem__("continue", calls["continue"] + 1) or False
        ),
        on_shutdown=lambda: calls.__setitem__(
            "shutdown", calls["shutdown"] + 1
        ),
    )
    connection = engine.attach_loop_client(client)

    assert connection.connected()
    assert bool(connection)
    engine.run()
    assert calls == {"poll": 1, "continue": 1, "shutdown": 1}

    connection.detach()
    assert not connection.connected()
    assert not connection


def test_python_loop_client_rejections_preserve_existing_connection() -> None:
    engine = EngineCore()
    calls = {"poll": 0}
    first = EngineLoopClient(
        poll_events=lambda: calls.__setitem__("poll", calls["poll"] + 1),
        should_continue=lambda: False,
        on_shutdown=lambda: None,
    )
    connection = engine.attach_loop_client(first)

    with pytest.raises(ValueError):
        engine.attach_loop_client(EngineLoopClient())
    assert connection.connected()

    second = EngineLoopClient(lambda: None, lambda: False, lambda: None)
    with pytest.raises(RuntimeError):
        engine.attach_loop_client(second)
    assert connection.connected()

    engine.target_fps = 0.0
    engine.run()
    assert calls["poll"] == 1


class _CallbackProbe:
    def __init__(self, result: bool | None = None) -> None:
        self.result = result

    def __call__(self) -> bool | None:
        return self.result


def test_detach_releases_consumed_python_callback_references() -> None:
    engine = EngineCore()
    poll = _CallbackProbe()
    should_continue = _CallbackProbe(False)
    shutdown = _CallbackProbe()
    callback_refs = [
        weakref.ref(poll),
        weakref.ref(should_continue),
        weakref.ref(shutdown),
    ]

    client = EngineLoopClient(poll, should_continue, shutdown)
    del poll, should_continue, shutdown
    connection = engine.attach_loop_client(client)
    gc.collect()
    assert all(callback_ref() is not None for callback_ref in callback_refs)

    connection.detach()
    gc.collect()
    assert all(callback_ref() is None for callback_ref in callback_refs)
