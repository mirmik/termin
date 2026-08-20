from __future__ import annotations

import pytest

from termin.engine import (
    EngineCore,
    WorldController,
    create_world_controller,
    publish_world_controllers,
    unregister_python_world_controller_owner,
)


def test_engine_core_reuses_null_runtime_session_without_placeholder() -> None:
    engine = EngineCore()

    assert engine.begin_session()
    assert engine.has_runtime_session
    assert not engine.begin_session()
    assert engine.end_session()
    assert not engine.has_runtime_session
    assert engine.begin_session(None)
    assert engine.end_session()
    assert engine.shutdown()


def test_engine_core_consumes_python_controller_and_preserves_context_identity() -> None:
    owner = "python_engine_runtime_session_test"
    events: list[tuple[str, object]] = []

    class ProjectDirector(WorldController):
        def start(self, context) -> None:
            assert context.valid
            self.context = context
            events.append(("start", context))

        def stop(self, context) -> None:
            assert context is self.context
            events.append(("stop", context))

        def __del__(self) -> None:
            events.append(("destroy", self.context))

    engine = EngineCore()
    try:
        publish_world_controllers([ProjectDirector], owner=owner)
        controller = create_world_controller("ProjectDirector")
        assert controller.valid
        assert controller.type_name == "ProjectDirector"

        assert engine.begin_session(controller)
        assert not controller.valid
        assert engine.has_runtime_session
        waiting_controller = create_world_controller("ProjectDirector")
        assert not engine.begin_session(waiting_controller)
        assert waiting_controller.valid
        assert engine.end_session()
        assert not engine.has_runtime_session
        assert engine.begin_session(waiting_controller)
        assert not waiting_controller.valid
        assert engine.end_session()
        assert [event for event, _context in events] == [
            "start",
            "stop",
            "destroy",
            "start",
            "stop",
            "destroy",
        ]
        assert events[0][1] is events[1][1]
        assert events[1][1] is events[2][1]
    finally:
        engine.shutdown()
        unregister_python_world_controller_owner(owner)


def test_failed_python_controller_start_leaves_no_runtime_session() -> None:
    owner = "python_engine_runtime_session_failure_test"
    events: list[str] = []

    class FailingDirector(WorldController):
        def start(self, context) -> None:
            events.append("start")
            raise RuntimeError("injected Python session failure")

        def stop(self, context) -> None:
            events.append("stop")

        def __del__(self) -> None:
            events.append("destroy")

    engine = EngineCore()
    try:
        publish_world_controllers([FailingDirector], owner=owner)
        controller = create_world_controller("FailingDirector")
        assert not engine.begin_session(controller)
        assert not controller.valid
        assert not engine.has_runtime_session
        assert events == ["start", "stop", "destroy"]
        assert engine.begin_session()
        assert engine.end_session()
    finally:
        engine.shutdown()
        unregister_python_world_controller_owner(owner)


def test_engine_core_rejects_wrong_python_session_owner_type() -> None:
    engine = EngineCore()
    with pytest.raises(TypeError, match="WorldControllerInstance or None"):
        engine.begin_session(object())
    assert not engine.has_runtime_session
    assert engine.shutdown()
