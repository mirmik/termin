import importlib.util
from pathlib import Path

from termin.engine import (
    EngineCore,
    SceneManager,
    WorldController,
    create_world_controller,
    publish_world_controllers,
    scene as engine_scene,
    unregister_python_world_controller_owner,
)
from termin.bootstrap import bootstrap_runtime

SceneMode = engine_scene.SceneMode


def _load_source_module(name: str, relative_path: str):
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GameModeModel = _load_source_module(
    "game_mode_model_under_test",
    "termin-app/termin/editor_core/game_mode_model.py",
).GameModeModel


class _RenderingController:
    editor_display = None

    sync_calls: list[str]
    sync_render_target_calls: list[str]
    attach_calls: list[str]
    detach_calls: list[str]

    def __init__(self):
        self.sync_calls = []
        self.sync_render_target_calls = []
        self.attach_calls = []
        self.detach_calls = []

    def sync_viewport_configs_to_scene(self, scene) -> None:
        self.sync_calls.append(scene.name)

    def sync_render_target_configs_to_scene(self, scene) -> None:
        self.sync_render_target_calls.append(scene.name)

    def attach_scene(self, scene) -> None:
        self.attach_calls.append(scene.name)

    def detach_scene(self, scene) -> None:
        self.detach_calls.append(scene.name)


class _CountingRenderingController:
    def __init__(self):
        self.editor_display = _Display()
        self.editor_render_target = _RenderTarget("(Editor)")
        self.editor_pipeline = _Pipeline()
        editor_viewport = _Viewport()
        editor_viewport.name = "(Editor)"
        editor_viewport.render_target = self.editor_render_target
        self.editor_display.viewports.append(editor_viewport)

        self.scene_displays = []
        self.render_targets = [self.editor_render_target]
        self.pipelines = [self.editor_pipeline]
        self.sync_calls = []
        self.sync_render_target_calls = []
        self.attach_calls = []
        self.detach_calls = []

    @property
    def counts(self):
        return {
            "editor_viewports": len(self.editor_display.viewports),
            "scene_displays": len(self.scene_displays),
            "scene_viewports": sum(len(display.viewports) for display in self.scene_displays),
            "render_targets": len(self.render_targets),
            "pipelines": len(self.pipelines),
        }

    def sync_viewport_configs_to_scene(self, scene) -> None:
        self.sync_calls.append(scene.name)

    def sync_render_target_configs_to_scene(self, scene) -> None:
        self.sync_render_target_calls.append(scene.name)

    def attach_scene(self, scene) -> None:
        self.attach_calls.append(scene.name)
        display = _Display()
        viewport = _Viewport()
        viewport.name = scene.name
        viewport.scene = scene
        render_target = _RenderTarget(f"{scene.name}.RT")
        pipeline = _Pipeline()
        render_target.scene = scene
        render_target.pipeline = pipeline
        viewport.render_target = render_target
        display.viewports.append(viewport)
        self.scene_displays.append(display)
        self.render_targets.append(render_target)
        self.pipelines.append(pipeline)

    def detach_scene(self, scene) -> None:
        self.detach_calls.append(scene.name)
        for display in list(self.scene_displays):
            kept = []
            for viewport in display.viewports:
                if viewport.scene is scene or viewport.scene.equal(scene):
                    render_target = viewport.render_target
                    if render_target in self.render_targets:
                        self.render_targets.remove(render_target)
                    pipeline = render_target.pipeline
                    if pipeline in self.pipelines:
                        self.pipelines.remove(pipeline)
                else:
                    kept.append(viewport)
            display.viewports = kept
            if not display.viewports:
                self.scene_displays.remove(display)


class _EditorAttachment:
    events: list[tuple]
    attached_scene_name: str | None

    def __init__(self):
        self.events = []
        self.attached_scene_name = None

    def save_state(self) -> None:
        self.events.append(("save_state",))

    def attach(
        self,
        scene,
        transfer_camera_state: bool = False,
        restore_state: bool = False,
    ) -> None:
        self.attached_scene_name = scene.name
        self.events.append(
            ("attach", scene.name, transfer_camera_state, restore_state)
        )

    def detach(self, save_state: bool = True) -> None:
        self.events.append(("detach", save_state))
        self.attached_scene_name = None


class _EditorConnector:
    events: list[tuple]
    attached_scene_name: str | None

    def __init__(self):
        self.events = []
        self.attached_scene_name = None
        self._failed_attach_scene_names: set[str] = set()

    def fail_next_attach(self, scene_name: str) -> None:
        self._failed_attach_scene_names.add(scene_name)

    def attach_editor_to_scene(
        self,
        scene_name: str,
        restore_state: bool = True,
        transfer_camera_state: bool = False,
        update_editor_scene_name: bool = True,
    ) -> bool:
        self.events.append(
            (
                "attach_editor_to_scene",
                scene_name,
                restore_state,
                transfer_camera_state,
                update_editor_scene_name,
            )
        )
        if scene_name in self._failed_attach_scene_names:
            self._failed_attach_scene_names.remove(scene_name)
            return False
        self.attached_scene_name = scene_name
        return True

    def detach_editor_from_scene(
        self,
        save_state: bool = True,
        clear_editor_scene_name: bool = True,
    ) -> bool:
        self.events.append(
            ("detach_editor_from_scene", save_state, clear_editor_scene_name)
        )
        self.attached_scene_name = None
        return True


class _RenderSession:
    events: list[tuple]

    def __init__(self):
        self.events = []
        self._failures: set[tuple[str, str]] = set()

    def fail_next(self, operation: str, scene_name: str) -> None:
        self._failures.add((operation, scene_name))

    def _should_fail(self, operation: str, scene_name: str) -> bool:
        key = (operation, scene_name)
        if key not in self._failures:
            return False
        self._failures.remove(key)
        return True

    def sync_scene_render_state(self, scene_name: str) -> bool:
        self.events.append(("sync_scene_render_state", scene_name))
        if self._should_fail("sync", scene_name):
            raise RuntimeError("injected render sync failure")
        return True

    def attach(self, scene_name: str) -> bool:
        self.events.append(("attach", scene_name))
        if self._should_fail("attach", scene_name):
            raise RuntimeError("injected render attach failure")
        return True

    def detach(
        self,
        scene_name: str,
        save_state: bool = True,
    ) -> bool:
        self.events.append(("detach", scene_name, save_state))
        if self._should_fail("detach", scene_name):
            raise RuntimeError("injected render detach failure")
        return True

    def reconcile_attached_scene(self, scene) -> bool:
        self.events.append(("reconcile", scene.name))
        if self._should_fail("reconcile", scene.name):
            raise RuntimeError("injected render presentation failure")
        return True


class _SceneTreeController:
    expanded_uuids: list[str]

    def __init__(self):
        self.expanded_uuids = ["entity-a", "entity-b"]

    def get_expanded_entity_uuids(self) -> list[str]:
        return list(self.expanded_uuids)


class _ViewportList:
    refresh_count: int

    def __init__(self):
        self.refresh_count = 0

    def refresh(self) -> None:
        self.refresh_count += 1


class _RenderingControllerForAttachment:
    attach_calls: list[str]
    render_target_refresh_count: int

    def __init__(self):
        self.attach_calls = []
        self._viewport_list = _ViewportList()
        self.render_target_refresh_count = 0
        self._manager = self

    def attach_scene(self, scene) -> None:
        self.attach_calls.append(scene.name)

    def _refresh_render_targets(self) -> None:
        self.render_target_refresh_count += 1

    def get_viewport_state(self, viewport):
        return None

    def register_viewport_attachment(self, display, viewport, destroy_on_scene_detach=True):
        return True

    def unregister_viewport_attachment(self, viewport):
        return True


class _Camera:
    def __init__(self):
        self.viewports = []

    def add_viewport(self, viewport) -> None:
        self.viewports.append(viewport)

    def remove_viewport(self, viewport) -> None:
        if viewport in self.viewports:
            self.viewports.remove(viewport)


class _CameraManager:
    def __init__(self, *, camera_overlay_factory=None):
        self.camera_overlay_factory = camera_overlay_factory
        self.camera = _Camera()
        self.editor_entities = _Entity()

    def attach_to_scene(self, scene) -> None:
        self.scene = scene

    def detach_from_scene(self) -> None:
        self.scene = None
        self.camera = None
        self.editor_entities = None

    def get_camera_data(self):
        return {"camera": "data"}

    def set_camera_data(self, data) -> None:
        self.camera_data = data


class _RenderTarget:
    def __init__(self, name="(Editor)"):
        self.name = name
        self.scene = None
        self.camera = None
        self.pipeline = None
        self.dynamic_resolution = False
        self.color_format = "rgba16f"
        self.depth_format = "depth32f"
        self.locked = False
        self.free_count = 0

    def free(self) -> None:
        self.free_count += 1


class _Pipeline:
    def __init__(self):
        self.destroy_count = 0

    def destroy(self) -> None:
        self.destroy_count += 1


class _Transform:
    children = []


class _Entity:
    components = []
    transform = _Transform()


class _Viewport:
    name = ""
    render_target = None
    internal_entities = None


class _Display:
    def __init__(self):
        self.viewports = []

    def create_viewport(self, scene, camera, rect):
        viewport = _Viewport()
        viewport.scene = scene
        viewport.render_target = type("_RenderTarget", (), {"camera": camera})()
        viewport.rect = rect
        self.viewports.append(viewport)
        return viewport

    def remove_viewport(self, viewport) -> None:
        if viewport in self.viewports:
            self.viewports.remove(viewport)


def _make_game_mode_model(
    engine,
    editor_connector,
    render_session,
    *,
    prepare_code_for_play=None,
    create_controller_for_play=None,
):
    return GameModeModel(
        engine=engine,
        editor_connector=editor_connector,
        render_scene_session=render_session,
        rendering_controller=_RenderingController(),
        get_editor_scene_name=lambda: "Editor",
        scene_tree_controller=_SceneTreeController(),
        prepare_code_for_play=prepare_code_for_play,
        create_controller_for_play=create_controller_for_play,
    )


def _new_game_mode_fixture():
    bootstrap_runtime()
    engine = EngineCore()
    editor_scene = engine.scene_manager.create_scene("Editor", [])
    assert editor_scene is not None
    engine.scene_manager.set_mode("Editor", SceneMode.STOP)
    editor_connector = _EditorConnector()
    editor_connector.attached_scene_name = "Editor"
    render_session = _RenderSession()
    model = _make_game_mode_model(engine, editor_connector, render_session)
    return engine, editor_scene, editor_connector, render_session, model


def _stop_and_shutdown(engine, model) -> None:
    if model.is_game_mode:
        model.toggle_game_mode()
    assert engine.shutdown()


def test_game_mode_model_routes_play_pause_and_stop_through_engine_session():
    engine, _editor_scene, connector, render_session, model = (
        _new_game_mode_fixture()
    )
    state_events = []
    mode_events = []
    model.state_changed.connect(
        lambda current: state_events.append(
            (current.is_game_mode, current.is_game_paused)
        )
    )
    model.mode_entered.connect(
        lambda playing, scene, expanded: mode_events.append(
            (playing, scene.name, expanded)
        )
    )

    try:
        model.toggle_game_mode()

        assert engine.has_runtime_session
        assert model.is_game_mode
        assert model.game_scene_name == "Editor(game)"
        assert engine.scene_manager.get_mode("Editor") == SceneMode.INACTIVE
        assert engine.scene_manager.get_mode("Editor(game)") == SceneMode.INACTIVE
        assert render_session.events == [
            ("sync_scene_render_state", "Editor"),
            ("detach", "Editor", False),
        ]
        assert connector.events == []
        assert state_events == [(True, False)]
        assert mode_events == []

        engine.tick_and_render(0.016)
        assert engine.scene_manager.get_mode("Editor(game)") == SceneMode.PLAY
        model.refresh_primary_scene()
        assert connector.attached_scene_name == "Editor(game)"
        assert render_session.events[-1] == ("reconcile", "Editor(game)")
        assert mode_events == [
            (True, "Editor(game)", ["entity-a", "entity-b"])
        ]

        model.toggle_pause()
        assert model.is_game_paused
        assert engine.has_runtime_session
        assert engine.scene_manager.get_mode("Editor(game)") == SceneMode.STOP
        model.toggle_pause()
        assert not model.is_game_paused
        assert engine.scene_manager.get_mode("Editor(game)") == SceneMode.PLAY

        model.toggle_game_mode()

        assert not engine.has_runtime_session
        assert not model.is_game_mode
        assert not engine.scene_manager.has_scene("Editor(game)")
        assert engine.scene_manager.get_mode("Editor") == SceneMode.STOP
        assert connector.attached_scene_name == "Editor"
        assert render_session.events[-2:] == [
            ("attach", "Editor"),
            ("reconcile", "Editor"),
        ]
        assert mode_events[-1] == (
            False,
            "Editor",
            ["entity-a", "entity-b"],
        )
    finally:
        _stop_and_shutdown(engine, model)


def test_game_mode_model_blocks_play_when_code_prepare_fails():
    engine, _editor_scene, connector, render_session, _model = (
        _new_game_mode_fixture()
    )
    model = _make_game_mode_model(
        engine,
        connector,
        render_session,
        prepare_code_for_play=lambda: False,
    )

    try:
        model.toggle_game_mode()

        assert not model.is_game_mode
        assert not engine.has_runtime_session
        assert not engine.scene_manager.has_scene("Editor(game)")
        assert engine.scene_manager.get_mode("Editor") == SceneMode.STOP
        assert connector.events == []
        assert render_session.events == []
    finally:
        _stop_and_shutdown(engine, model)


def test_selected_controller_starts_before_runtime_copy_and_stops_before_close():
    owner = "editor-game-mode-controller-owner"
    events = []
    engine, _editor_scene, connector, render_session, _model = (
        _new_game_mode_fixture()
    )

    class EditorDirector(WorldController):
        def start(self, _context) -> None:
            assert not engine.scene_manager.has_scene("Editor(game)")
            events.append("controller:start")

        def stop(self, _context) -> None:
            assert engine.scene_manager.has_scene("Editor(game)")
            events.append("controller:stop")

    publish_world_controllers([EditorDirector], owner=owner)
    model = _make_game_mode_model(
        engine,
        connector,
        render_session,
        prepare_code_for_play=lambda: events.append("modules:ready") or True,
        create_controller_for_play=lambda: (
            events.append("controller:create")
            or create_world_controller("EditorDirector", owner)
        ),
    )

    try:
        model.toggle_game_mode()
        assert events == [
            "modules:ready",
            "controller:create",
            "controller:start",
        ]
        engine.tick_and_render(0.0)
        model.refresh_primary_scene()
        model.toggle_game_mode()
        assert events == [
            "modules:ready",
            "controller:create",
            "controller:start",
            "controller:stop",
        ]
    finally:
        _stop_and_shutdown(engine, model)
        unregister_python_world_controller_owner(owner)


def test_failed_play_setup_ends_session_and_restores_authoring_scene():
    engine, _editor_scene, connector, render_session, _model = (
        _new_game_mode_fixture()
    )
    render_session.fail_next("detach", "Editor")
    model = _make_game_mode_model(engine, connector, render_session)

    try:
        model.toggle_game_mode()

        assert not model.is_game_mode
        assert not engine.has_runtime_session
        assert not engine.scene_manager.has_scene("Editor(game)")
        assert engine.scene_manager.get_mode("Editor") == SceneMode.STOP
        assert render_session.events == [
            ("sync_scene_render_state", "Editor"),
            ("detach", "Editor", False),
        ]
    finally:
        _stop_and_shutdown(engine, model)


def test_editor_presentation_failure_does_not_roll_back_committed_primary():
    engine, _editor_scene, connector, render_session, model = (
        _new_game_mode_fixture()
    )
    connector.fail_next_attach("Editor(game)")

    try:
        model.toggle_game_mode()
        runtime_scene = engine.scene_manager.get_scene("Editor(game)")
        assert runtime_scene is not None
        engine.tick_and_render(0.0)
        model.refresh_primary_scene()

        context = model._game_session.context
        assert context.primary_scene.name == "Editor(game)"
        assert engine.rendering_manager.topology.is_attached(runtime_scene)
        assert engine.scene_manager.get_mode("Editor(game)") == SceneMode.PLAY
        assert model.is_game_mode
        assert connector.attached_scene_name == "Editor"
    finally:
        _stop_and_shutdown(engine, model)


def test_game_mode_model_observes_rotation_without_host_transition_binding():
    engine, _editor_scene, connector, render_session, model = (
        _new_game_mode_fixture()
    )
    secondary = None

    try:
        model.toggle_game_mode()
        engine.tick_and_render(0.0)
        model.refresh_primary_scene()

        secondary = engine.scene_manager.create_scene("Secondary(game)", [])
        assert secondary is not None
        assert engine.bind_runtime_scene(secondary)
        context = model._game_session.context
        assert context.request_primary_scene(secondary)

        engine.tick_and_render(0.0)
        model.refresh_primary_scene()

        assert model.game_scene_name == "Secondary(game)"
        assert connector.attached_scene_name == "Secondary(game)"
        assert render_session.events[-1] == ("reconcile", "Secondary(game)")
        assert engine.scene_manager.get_mode("Editor(game)") == SceneMode.INACTIVE
        assert engine.scene_manager.get_mode("Secondary(game)") == SceneMode.PLAY

        model.toggle_game_mode()
        assert not context.valid
        assert engine.scene_manager.has_scene("Secondary(game)")
        assert engine.scene_manager.get_mode("Secondary(game)") == SceneMode.INACTIVE
    finally:
        _stop_and_shutdown(engine, model)
        if (
            secondary is not None
            and engine.scene_manager.has_scene("Secondary(game)")
        ):
            engine.scene_manager.close_scene("Secondary(game)")


def test_game_mode_model_supports_repeated_play_stop_cycles():
    engine, _editor_scene, connector, render_session, model = (
        _new_game_mode_fixture()
    )

    try:
        for _ in range(3):
            model.toggle_game_mode()
            assert model.is_game_mode
            assert engine.has_runtime_session
            engine.tick_and_render(0.0)
            model.refresh_primary_scene()
            model.toggle_game_mode()
            assert not model.is_game_mode
            assert not engine.has_runtime_session
            assert not engine.scene_manager.has_scene("Editor(game)")
        assert connector.attached_scene_name == "Editor"
        assert engine.scene_manager.get_mode("Editor") == SceneMode.STOP
    finally:
        _stop_and_shutdown(engine, model)


def test_editor_scene_attachment_reuses_editor_render_target(monkeypatch):
    from termin.editor_core import editor_camera
    import termin.render_framework._render_framework_native as render_framework_native

    EditorSceneAttachment = _load_source_module(
        "editor_scene_attachment_under_test",
        "termin-app/termin/editor_core/editor_scene_attachment.py",
    ).EditorSceneAttachment

    monkeypatch.setattr(editor_camera, "EditorCameraManager", _CameraManager)
    render_targets = []

    def _new_render_target(name):
        rt = _RenderTarget(name)
        render_targets.append(rt)
        return rt

    monkeypatch.setattr(render_framework_native, "render_target_new", _new_render_target)

    scene_manager = SceneManager()
    scene = scene_manager.create_scene("Editor", [])
    game_scene = scene_manager.create_scene("Editor(game)", [])
    assert scene is not None
    assert game_scene is not None

    rendering = _RenderingControllerForAttachment()
    pipeline = _Pipeline()
    attachment = EditorSceneAttachment(
        display=_Display(),
        rendering_controller=rendering,
        rendering_manager=rendering._manager,
        make_editor_pipeline=lambda: pipeline,
    )

    try:
        attachment.attach(scene, restore_state=False)
        first_rt = attachment.viewport.render_target

        attachment.attach(game_scene, transfer_camera_state=True)

        assert attachment.scene is game_scene
        assert attachment.viewport is not None
        assert attachment.viewport.render_target is first_rt
        assert len(render_targets) == 1
        assert first_rt.free_count == 0
        assert pipeline.destroy_count == 0
        assert first_rt.scene is game_scene
        assert first_rt.camera is attachment.camera
        assert first_rt.pipeline is pipeline
        assert first_rt.dynamic_resolution is True
        assert first_rt.locked is True
        assert rendering.attach_calls == []
        assert rendering._viewport_list.refresh_count == 3
        assert rendering.render_target_refresh_count == 3
    finally:
        scene_manager.close_all_scenes()
