import importlib.util
from pathlib import Path

from termin.engine import SceneManager, scene as engine_scene

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


PrimaryRenderSceneBinding = _load_source_module(
    "primary_render_scene_binding_under_test",
    "termin-app/termin/editor_core/primary_render_scene_binding.py",
).PrimaryRenderSceneBinding
GameModeModel = _load_source_module(
    "game_mode_model_under_test",
    "termin-app/termin/editor_core/game_mode_model.py",
).GameModeModel
RenderSceneAttachment = _load_source_module(
    "render_scene_attachment_under_test",
    "termin-app/termin/editor_core/render_scene_attachment.py",
).RenderSceneAttachment


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


class _RenderConnector:
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
        return not self._should_fail("sync", scene_name)

    def attach_scene_to_render(self, scene_name: str) -> bool:
        self.events.append(("attach_scene_to_render", scene_name))
        return not self._should_fail("attach", scene_name)

    def detach_scene_from_render(
        self,
        scene_name: str,
        save_state: bool = True,
    ) -> bool:
        self.events.append(("detach_scene_from_render", scene_name, save_state))
        return not self._should_fail("detach", scene_name)


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


def _make_game_mode_model(scene_manager, editor_connector, render_connector):
    return GameModeModel(
        scene_manager=scene_manager,
        editor_connector=editor_connector,
        rendering_controller=_RenderingController(),
        get_editor_scene_name=lambda: "Editor",
        render_binding_factory=lambda scene_name: PrimaryRenderSceneBinding(
            render_connector,
            scene_name,
        ),
    )


def test_game_mode_model_switches_scene_modes_rendering_and_editor_attachments():
    scene_manager = SceneManager()
    editor_scene = scene_manager.create_scene("Editor", [])
    assert editor_scene is not None
    scene_manager.set_mode("Editor", SceneMode.STOP)

    rendering = _RenderingController()
    connector = _EditorConnector()
    render_connector = _RenderConnector()
    tree = _SceneTreeController()
    prepare_calls = []

    model = GameModeModel(
        scene_manager=scene_manager,
        editor_connector=connector,
        rendering_controller=rendering,
        get_editor_scene_name=lambda: "Editor",
        render_binding_factory=lambda scene_name: PrimaryRenderSceneBinding(
            render_connector,
            scene_name,
        ),
        scene_tree_controller=tree,
        prepare_code_for_play=lambda: prepare_calls.append("prepare") or True,
    )

    state_events = []
    mode_events = []
    model.state_changed.connect(lambda m: state_events.append((m.is_game_mode, m.is_game_paused)))
    model.mode_entered.connect(
        lambda is_playing, scene, expanded: mode_events.append(
            (is_playing, scene.name if scene is not None else None, expanded)
        )
    )

    try:
        model.toggle_game_mode()

        assert prepare_calls == ["prepare"]
        assert model.is_game_mode is True
        assert model.is_game_paused is False
        assert model.game_scene_name == "Editor(game)"
        assert scene_manager.has_scene("Editor")
        assert scene_manager.has_scene("Editor(game)")
        assert scene_manager.get_mode("Editor") == SceneMode.INACTIVE
        assert scene_manager.get_mode("Editor(game)") == SceneMode.PLAY
        assert scene_manager.has_play_scenes() is True
        assert rendering.sync_calls == []
        assert rendering.sync_render_target_calls == []
        assert rendering.detach_calls == []
        assert rendering.attach_calls == []
        assert render_connector.events == [
            ("sync_scene_render_state", "Editor"),
            ("attach_scene_to_render", "Editor(game)"),
            ("detach_scene_from_render", "Editor", False),
        ]
        assert connector.events == [
            (
                "attach_editor_to_scene",
                "Editor(game)",
                False,
                True,
                False,
            ),
        ]
        assert connector.attached_scene_name == "Editor(game)"
        assert state_events == [(True, False)]
        assert mode_events == [(True, "Editor(game)", ["entity-a", "entity-b"])]

        model.toggle_pause()
        assert model.is_game_paused is True
        assert scene_manager.get_mode("Editor(game)") == SceneMode.STOP
        assert scene_manager.has_play_scenes() is False

        model.toggle_pause()
        assert model.is_game_paused is False
        assert scene_manager.get_mode("Editor(game)") == SceneMode.PLAY
        assert scene_manager.has_play_scenes() is True

        model.toggle_game_mode()

        assert model.is_game_mode is False
        assert model.is_game_paused is False
        assert model.game_scene_name is None
        assert scene_manager.has_scene("Editor") is True
        assert scene_manager.has_scene("Editor(game)") is False
        assert scene_manager.get_mode("Editor") == SceneMode.STOP
        assert scene_manager.has_play_scenes() is False
        assert rendering.detach_calls == []
        assert rendering.attach_calls == []
        assert render_connector.events == [
            ("sync_scene_render_state", "Editor"),
            ("attach_scene_to_render", "Editor(game)"),
            ("detach_scene_from_render", "Editor", False),
            ("attach_scene_to_render", "Editor"),
            ("detach_scene_from_render", "Editor(game)", False),
        ]
        assert connector.events == [
            (
                "attach_editor_to_scene",
                "Editor(game)",
                False,
                True,
                False,
            ),
            (
                "attach_editor_to_scene",
                "Editor",
                True,
                False,
                True,
            ),
        ]
        assert connector.attached_scene_name == "Editor"
        assert state_events == [
            (True, False),
            (True, True),
            (True, False),
            (False, False),
        ]
        assert mode_events[-1] == (False, "Editor", ["entity-a", "entity-b"])
    finally:
        scene_manager.close_all_scenes()


def test_game_mode_model_blocks_play_when_code_prepare_fails():
    scene_manager = SceneManager()
    editor_scene = scene_manager.create_scene("Editor", [])
    assert editor_scene is not None
    scene_manager.set_mode("Editor", SceneMode.STOP)

    connector = _EditorConnector()
    render_connector = _RenderConnector()
    model = GameModeModel(
        scene_manager=scene_manager,
        editor_connector=connector,
        rendering_controller=_RenderingController(),
        get_editor_scene_name=lambda: "Editor",
        render_binding_factory=lambda scene_name: PrimaryRenderSceneBinding(
            render_connector,
            scene_name,
        ),
        prepare_code_for_play=lambda: False,
    )

    try:
        model.toggle_game_mode()

        assert model.is_game_mode is False
        assert scene_manager.has_scene("Editor(game)") is False
        assert scene_manager.get_mode("Editor") == SceneMode.STOP
        assert connector.events == []
        assert render_connector.events == []
    finally:
        scene_manager.close_all_scenes()


def test_game_mode_model_rolls_back_failed_start_render_rebind():
    scene_manager = SceneManager()
    editor_scene = scene_manager.create_scene("Editor", [])
    assert editor_scene is not None
    scene_manager.set_mode("Editor", SceneMode.STOP)
    editor_connector = _EditorConnector()
    editor_connector.attached_scene_name = "Editor"
    render_connector = _RenderConnector()
    render_connector.fail_next("attach", "Editor(game)")
    model = _make_game_mode_model(
        scene_manager,
        editor_connector,
        render_connector,
    )
    state_events = []
    model.state_changed.connect(lambda _model: state_events.append("changed"))

    try:
        model.toggle_game_mode()

        assert model.is_game_mode is False
        assert scene_manager.has_scene("Editor(game)") is False
        assert scene_manager.get_mode("Editor") == SceneMode.STOP
        assert editor_connector.attached_scene_name == "Editor"
        assert state_events == []
    finally:
        scene_manager.close_all_scenes()


def test_game_mode_model_rolls_back_failed_start_editor_switch():
    scene_manager = SceneManager()
    editor_scene = scene_manager.create_scene("Editor", [])
    assert editor_scene is not None
    scene_manager.set_mode("Editor", SceneMode.STOP)
    editor_connector = _EditorConnector()
    editor_connector.attached_scene_name = "Editor"
    editor_connector.fail_next_attach("Editor(game)")
    render_connector = _RenderConnector()
    model = _make_game_mode_model(
        scene_manager,
        editor_connector,
        render_connector,
    )

    try:
        model.toggle_game_mode()

        assert model.is_game_mode is False
        assert scene_manager.has_scene("Editor(game)") is False
        assert scene_manager.get_mode("Editor") == SceneMode.STOP
        assert editor_connector.attached_scene_name == "Editor"
        assert render_connector.events[-2:] == [
            ("attach_scene_to_render", "Editor"),
            ("detach_scene_from_render", "Editor(game)", False),
        ]
    finally:
        scene_manager.close_all_scenes()


def test_game_mode_model_keeps_playing_when_stop_render_rebind_fails():
    scene_manager = SceneManager()
    editor_scene = scene_manager.create_scene("Editor", [])
    assert editor_scene is not None
    scene_manager.set_mode("Editor", SceneMode.STOP)
    editor_connector = _EditorConnector()
    editor_connector.attached_scene_name = "Editor"
    render_connector = _RenderConnector()
    model = _make_game_mode_model(
        scene_manager,
        editor_connector,
        render_connector,
    )

    try:
        model.toggle_game_mode()
        render_connector.fail_next("attach", "Editor")
        model.toggle_game_mode()

        assert model.is_game_mode is True
        assert scene_manager.has_scene("Editor(game)") is True
        assert scene_manager.get_mode("Editor") == SceneMode.INACTIVE
        assert scene_manager.get_mode("Editor(game)") == SceneMode.PLAY
        assert editor_connector.attached_scene_name == "Editor(game)"
    finally:
        scene_manager.close_all_scenes()


def test_game_mode_model_rolls_back_failed_stop_editor_switch():
    scene_manager = SceneManager()
    editor_scene = scene_manager.create_scene("Editor", [])
    assert editor_scene is not None
    scene_manager.set_mode("Editor", SceneMode.STOP)
    editor_connector = _EditorConnector()
    editor_connector.attached_scene_name = "Editor"
    render_connector = _RenderConnector()
    model = _make_game_mode_model(
        scene_manager,
        editor_connector,
        render_connector,
    )

    try:
        model.toggle_game_mode()
        editor_connector.fail_next_attach("Editor")
        model.toggle_game_mode()

        assert model.is_game_mode is True
        assert scene_manager.has_scene("Editor(game)") is True
        assert scene_manager.get_mode("Editor") == SceneMode.INACTIVE
        assert scene_manager.get_mode("Editor(game)") == SceneMode.PLAY
        assert editor_connector.attached_scene_name == "Editor(game)"
        assert render_connector.events[-2:] == [
            ("attach_scene_to_render", "Editor(game)"),
            ("detach_scene_from_render", "Editor", False),
        ]
    finally:
        scene_manager.close_all_scenes()


def test_game_mode_model_supports_repeated_play_stop_cycles():
    scene_manager = SceneManager()
    editor_scene = scene_manager.create_scene("Editor", [])
    assert editor_scene is not None
    scene_manager.set_mode("Editor", SceneMode.STOP)
    editor_connector = _EditorConnector()
    editor_connector.attached_scene_name = "Editor"
    render_connector = _RenderConnector()
    model = _make_game_mode_model(
        scene_manager,
        editor_connector,
        render_connector,
    )

    try:
        for _ in range(3):
            model.toggle_game_mode()
            assert model.is_game_mode is True
            assert scene_manager.has_scene("Editor(game)") is True
            model.toggle_game_mode()
            assert model.is_game_mode is False
            assert scene_manager.has_scene("Editor(game)") is False
        assert editor_connector.attached_scene_name == "Editor"
        assert scene_manager.get_mode("Editor") == SceneMode.STOP
    finally:
        scene_manager.close_all_scenes()


def test_game_mode_model_restores_render_counts_with_shared_render_attachment():
    scene_manager = SceneManager()
    editor_scene = scene_manager.create_scene("Editor", [])
    assert editor_scene is not None
    scene_manager.set_mode("Editor", SceneMode.STOP)

    rendering = _CountingRenderingController()
    render_attachment = RenderSceneAttachment(scene_manager, rendering)
    render_attachment.attach_scene_to_render("Editor")
    baseline = rendering.counts

    connector = _EditorConnector()
    model = GameModeModel(
        scene_manager=scene_manager,
        editor_connector=connector,
        rendering_controller=rendering,
        get_editor_scene_name=lambda: "Editor",
        render_binding_factory=lambda scene_name: PrimaryRenderSceneBinding(
            render_attachment,
            scene_name,
        ),
    )

    try:
        model.toggle_game_mode()

        assert rendering.counts == baseline
        assert rendering.sync_calls == ["Editor"]
        assert rendering.sync_render_target_calls == ["Editor"]
        assert rendering.detach_calls == ["Editor"]
        assert rendering.attach_calls == ["Editor", "Editor(game)"]
        assert rendering.editor_display.viewports[0].render_target is rendering.editor_render_target
        assert scene_manager.get_mode("Editor") == SceneMode.INACTIVE
        assert scene_manager.get_mode("Editor(game)") == SceneMode.PLAY

        model.toggle_game_mode()

        assert rendering.counts == baseline
        assert rendering.detach_calls == ["Editor", "Editor(game)"]
        assert rendering.attach_calls == ["Editor", "Editor(game)", "Editor"]
        assert rendering.editor_display.viewports[0].render_target is rendering.editor_render_target
        assert scene_manager.get_mode("Editor") == SceneMode.STOP
        assert scene_manager.has_scene("Editor(game)") is False
    finally:
        scene_manager.close_all_scenes()


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
