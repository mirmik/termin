import sys
import types

from termin.editor_tcgui.render_target_inspector import RenderTargetInspectorTcgui


class _ResourceManager:
    def list_pipeline_names(self):
        return []


class _CameraComponent:
    pass


class _Entity:
    def __init__(self, name, camera):
        self.name = name
        self.uuid = name
        self._camera = camera

    def get_component(self, component_type):
        assert component_type is _CameraComponent
        return self._camera


class _SceneHandle:
    def __init__(self, index):
        self.index = index


class _Scene:
    def __init__(self, name, index, entities):
        self.name = name
        self.uuid = name
        self.entities = entities
        self._handle = _SceneHandle(index)

    def scene_handle(self):
        return self._handle


class _RenderTarget:
    def __init__(self, scene, camera):
        self.name = "Target"
        self.enabled = True
        self.locked = False
        self.scene = scene
        self.camera = camera
        self.pipeline = None
        self.dynamic_resolution = True
        self.width = 320
        self.height = 200


def test_render_target_inspector_reads_camera_from_render_target_scene(monkeypatch):
    camera_module = types.ModuleType("termin.visualization.core.camera")
    camera_module.CameraComponent = _CameraComponent
    monkeypatch.setitem(sys.modules, "termin.visualization.core.camera", camera_module)

    editor_camera = _CameraComponent()
    game_camera = _CameraComponent()
    editor_scene = _Scene("Editor", 1, [_Entity("EditorCamera", editor_camera)])
    game_scene = _Scene("Editor(game)", 2, [_Entity("GameCamera", game_camera)])
    render_target = _RenderTarget(game_scene, game_camera)

    inspector = RenderTargetInspectorTcgui(_ResourceManager())
    inspector.set_scene_getter(lambda: [editor_scene, game_scene])
    inspector.set_render_target(render_target, editor_scene)

    assert inspector._scene is game_scene
    assert inspector._cameras == [game_camera]
    assert inspector._camera_combo.selected_index == 1
