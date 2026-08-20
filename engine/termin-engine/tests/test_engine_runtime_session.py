from __future__ import annotations

import pytest

from termin.engine import (
    EngineCore,
    WorldController,
    create_world_controller,
    publish_world_controllers,
    register_default_scene_extensions,
    require_world_context,
    scene as engine_scene,
    unregister_python_world_controller_owner,
    world_context,
)
from termin.scene import PythonComponent


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


def test_runtime_session_rejects_authoring_scene_binding() -> None:
    engine = EngineCore()
    scene = engine.scene_manager.create_scene(
        engine_scene.SceneKey("python-authoring-scene", engine_scene.SceneRole.AUTHORING)
    )
    assert scene is not None

    assert engine.begin_session()
    assert not engine.bind_runtime_scene(scene)
    assert not world_context(scene).valid
    assert engine.end_session()
    assert engine.shutdown()


def test_engine_core_consumes_python_controller_and_preserves_context_identity() -> None:
    owner = "python_engine_runtime_session_test"
    events: list[tuple[str, object]] = []

    class ProjectDirector(WorldController):
        runtime_value = "world-state"

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
        scene = engine.scene_manager.create_scene(
            engine_scene.SceneKey(
                "python-controller-runtime-scene", engine_scene.SceneRole.RUNTIME
            )
        )
        assert scene is not None
        assert engine.bind_runtime_scene(scene)
        scene_context = world_context(scene)
        assert scene_context.valid
        assert scene_context == events[0][1]
        controller_view = scene_context.controller
        assert controller_view is not None
        assert isinstance(controller_view, ProjectDirector)
        assert controller_view.runtime_value == "world-state"
        assert controller_view.context is events[0][1]
        waiting_controller = create_world_controller("ProjectDirector")
        assert not engine.begin_session(waiting_controller)
        assert waiting_controller.valid
        assert engine.end_session()
        assert not engine.has_runtime_session
        assert not scene_context.valid
        with pytest.raises(ReferenceError):
            _ = controller_view.runtime_value
        assert not world_context(scene).valid
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


def test_null_session_context_is_transient_and_available_to_python_lifecycle() -> None:
    class SceneContextProbe(PythonComponent):
        def __init__(self) -> None:
            super().__init__()
            self.active_context = None
            self.start_context = None

        def on_scene_active(self) -> None:
            self.active_context = require_world_context(
                self.scene, "SceneContextProbe.on_scene_active"
            )

        def start(self) -> None:
            self.start_context = require_world_context(
                self.scene, "SceneContextProbe.start"
            )

    engine = EngineCore()
    scene_key = engine_scene.SceneKey(
        "python-null-controller-runtime-scene", engine_scene.SceneRole.RUNTIME
    )
    scene = engine.scene_manager.create_scene(scene_key)
    assert scene is not None
    entity = scene.create_entity("context-probe")
    component = SceneContextProbe()
    entity.add_component(component)

    authoring_context = world_context(scene)
    assert not authoring_context.valid
    with pytest.raises(RuntimeError, match="AuthoringProbe requires"):
        require_world_context(scene, "AuthoringProbe")

    assert engine.begin_session()
    assert not world_context(scene).valid
    assert engine.bind_runtime_scene(scene)
    retained = world_context(scene)
    assert retained.valid
    assert retained.controller is None

    serialized = scene.serialize()
    assert "world_context" not in serialized.get("extensions", {})
    copied = engine.scene_manager.copy_scene(
        scene_key,
        engine_scene.SceneKey(
            "python-null-controller-runtime-scene-copy",
            engine_scene.SceneRole.RUNTIME,
        ),
    )
    assert copied is not None
    assert not world_context(copied).valid

    engine.scene_manager.set_mode(
        scene_key, engine_scene.SceneMode.PLAY
    )
    assert component.active_context == retained
    assert engine.tick(0.016)
    assert component.start_context == retained

    assert engine.end_session()
    assert scene.is_alive()
    assert not world_context(scene).valid
    assert not retained.valid
    assert not component.active_context.valid
    assert not component.start_context.valid
    assert engine.shutdown()


def test_python_component_requests_primary_scene_for_next_engine_tick() -> None:
    register_default_scene_extensions()
    events: list[str] = []

    class TransitionProbe(PythonComponent):
        def __init__(self, label: str) -> None:
            super().__init__()
            self.label = label
            self.target = None

        def on_scene_active(self) -> None:
            events.append(f"{self.label}:active")

        def on_scene_inactive(self) -> None:
            events.append(f"{self.label}:inactive")

        def update(self, _dt: float) -> None:
            events.append(f"{self.label}:update")
            if self.target is not None:
                context = require_world_context(self.scene, "TransitionProbe.update")
                assert context.transition_to(self.target)
                self.target = None

    engine = EngineCore()
    first = engine.scene_manager.create_scene(
        engine_scene.SceneKey("python-primary-first", engine_scene.SceneRole.RUNTIME)
    )
    second = engine.scene_manager.create_scene(
        engine_scene.SceneKey("python-primary-second", engine_scene.SceneRole.RUNTIME)
    )
    assert first is not None
    assert second is not None
    first_entity = first.create_entity("first-probe")
    first_probe = TransitionProbe("first")
    first_entity.add_component(first_probe)
    second_entity = second.create_entity("second-probe")
    second_entity.add_component(TransitionProbe("second"))

    assert engine.begin_session()
    assert engine.bind_runtime_scene(first)
    assert engine.bind_runtime_scene(second)
    context = require_world_context(first, "Python transition test")
    assert context.primary_scene is None
    assert context.scene_identities == ("python-primary-first", "python-primary-second")
    assert isinstance(context.scene_identities, tuple)
    assert not context.transition_to("missing.scene")
    assert context.transition_to("python-primary-first")
    assert not context.transition_to("python-primary-second")

    assert engine.tick_and_render(0.016)
    assert context.primary_scene.name == first.name
    assert events == ["first:active", "first:update"]

    events.clear()
    first_probe.target = "python-primary-second"
    assert engine.tick_and_render(0.016)
    assert context.primary_scene.name == first.name
    assert events == ["first:update"]

    events.clear()
    assert engine.tick_and_render(0.016)
    assert context.primary_scene.name == second.name
    assert events == ["first:inactive", "second:active", "second:update"]

    assert engine.end_session()
    assert context.primary_scene is None
    assert not context.valid
    assert engine.shutdown()
