import importlib.util
from pathlib import Path

from termin.editor.scene_manager import SceneManager, SceneMode


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


class _ProjectModulesRuntime:
    rebuild_count: int

    def __init__(self):
        self.rebuild_count = 0

    def rebuild_stale_modules(self) -> None:
        self.rebuild_count += 1


class _RenderingController:
    editor_display = None

    sync_calls: list[str]
    attach_calls: list[str]
    detach_calls: list[str]

    def __init__(self):
        self.sync_calls = []
        self.attach_calls = []
        self.detach_calls = []

    def sync_viewport_configs_to_scene(self, scene) -> None:
        self.sync_calls.append(scene.name)

    def attach_scene(self, scene) -> None:
        self.attach_calls.append(scene.name)

    def detach_scene(self, scene) -> None:
        self.detach_calls.append(scene.name)


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
        self.offscreen_context = None

    def attach_scene(self, scene) -> None:
        self.attach_calls.append(scene.name)

    def _refresh_render_targets(self) -> None:
        self.render_target_refresh_count += 1

    def get_viewport_state(self, viewport):
        return None


class _Camera:
    def __init__(self):
        self.viewports = []

    def add_viewport(self, viewport) -> None:
        self.viewports.append(viewport)

    def remove_viewport(self, viewport) -> None:
        if viewport in self.viewports:
            self.viewports.remove(viewport)


class _CameraManager:
    def __init__(self):
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
        viewport.camera = camera
        viewport.rect = rect
        self.viewports.append(viewport)
        return viewport

    def remove_viewport(self, viewport) -> None:
        if viewport in self.viewports:
            self.viewports.remove(viewport)


def test_game_mode_model_switches_scene_modes_rendering_and_editor_attachments(monkeypatch):
    import termin.modules

    runtime = _ProjectModulesRuntime()
    monkeypatch.setattr(
        termin.modules,
        "get_project_modules_runtime",
        lambda: runtime,
    )

    scene_manager = SceneManager()
    editor_scene = scene_manager.create_scene("Editor", [])
    assert editor_scene is not None
    scene_manager.set_mode("Editor", SceneMode.STOP)

    rendering = _RenderingController()
    attachment = _EditorAttachment()
    tree = _SceneTreeController()

    model = GameModeModel(
        scene_manager=scene_manager,
        editor_attachment=attachment,
        rendering_controller=rendering,
        get_editor_scene_name=lambda: "Editor",
        scene_tree_controller=tree,
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

        assert runtime.rebuild_count == 1
        assert model.is_game_mode is True
        assert model.is_game_paused is False
        assert model.game_scene_name == "Editor(game)"
        assert scene_manager.has_scene("Editor")
        assert scene_manager.has_scene("Editor(game)")
        assert scene_manager.get_mode("Editor") == SceneMode.INACTIVE
        assert scene_manager.get_mode("Editor(game)") == SceneMode.PLAY
        assert scene_manager.has_play_scenes() is True
        assert rendering.sync_calls == ["Editor"]
        assert rendering.detach_calls == ["Editor"]
        assert rendering.attach_calls == ["Editor(game)"]
        assert attachment.events == [
            ("save_state",),
            ("attach", "Editor(game)", True, False),
        ]
        assert attachment.attached_scene_name == "Editor(game)"
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
        assert rendering.detach_calls == ["Editor", "Editor(game)"]
        assert rendering.attach_calls == ["Editor(game)", "Editor"]
        assert attachment.events == [
            ("save_state",),
            ("attach", "Editor(game)", True, False),
            ("detach", False),
            ("attach", "Editor", False, True),
        ]
        assert attachment.attached_scene_name == "Editor"
        assert state_events == [
            (True, False),
            (True, True),
            (True, False),
            (False, False),
        ]
        assert mode_events[-1] == (False, "Editor", ["entity-a", "entity-b"])
    finally:
        scene_manager.close_all_scenes()


def test_editor_scene_attachment_reuses_editor_render_target(monkeypatch):
    from termin.editor import editor_camera
    import termin.render_framework._render_framework_native as render_framework_native

    EditorSceneAttachment = _load_source_module(
        "editor_scene_attachment_under_test",
        "termin-app/termin/editor/editor_scene_attachment.py",
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
        assert first_rt.locked is True
        assert rendering.attach_calls == []
        assert rendering._viewport_list.refresh_count == 3
        assert rendering.render_target_refresh_count == 3
    finally:
        scene_manager.close_all_scenes()
