import sys
import types

from termin.editor_tcgui.render_target_inspector import RenderTargetInspectorTcgui
from termin.editor_tcgui.widgets.texture_picker import TexturePickerWidget


class _ResourceManager:
    def list_pipeline_names(self):
        return []

    def list_texture_names(self):
        return []

    def get_texture_asset(self, name):
        return None

    def get_texture_asset_by_uuid(self, uuid):
        return None

    def get_texture(self, name):
        return None

    def get_pipeline_asset(self, name):
        return None

    def get_scene_pipeline_asset(self, name):
        return None


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
        self.color_format = "rgba16f"
        self.depth_format = "depth32f"
        self.clear_color_enabled = False
        self.clear_color_value = (0.0, 0.0, 0.0, 1.0)
        self.clear_depth_enabled = False
        self.clear_depth_value = 1.0
        self.layer_mask = 0xFFFFFFFF
        self.pipeline_params = {}


class _Pipeline:
    def __init__(self, name):
        self.name = name


class _PipelineAsset:
    def __init__(self, external_params):
        self.external_params = external_params


class _TextureAsset:
    def __init__(self, name, uuid):
        self.name = name
        self.uuid = uuid


class _TextureResourceManager(_ResourceManager):
    def __init__(self):
        self._textures = {
            "Grenade": _TextureAsset("Grenade", "texture-uuid-grenade"),
        }

    def list_pipeline_names(self):
        return ["Pipe"]

    def list_texture_names(self):
        return list(self._textures.keys())

    def get_texture_asset(self, name):
        return self._textures.get(name)

    def get_texture_asset_by_uuid(self, uuid):
        for asset in self._textures.values():
            if asset.uuid == uuid:
                return asset
        return None

    def get_texture(self, name):
        if name in self._textures:
            return types.SimpleNamespace(_image_data=None)
        return None

    def get_pipeline_asset(self, name):
        if name == "Pipe":
            return _PipelineAsset(["input_texture"])
        return None


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


def test_render_target_inspector_pipeline_params_use_texture_preview(monkeypatch):
    texture_module = types.ModuleType("termin.visualization.render.texture")
    texture_module.get_white_texture = lambda: types.SimpleNamespace(_image_data=None)
    texture_module.get_normal_texture = lambda: types.SimpleNamespace(_image_data=None)
    monkeypatch.setitem(sys.modules, "termin.visualization.render.texture", texture_module)

    scene_mount_module = types.ModuleType("termin.visualization.core.scene")
    scene_mount_module.scene_render_mount = lambda scene: types.SimpleNamespace(render_target_configs=[])
    monkeypatch.setitem(sys.modules, "termin.visualization.core.scene", scene_mount_module)

    scene = _Scene("Scene", 1, [])
    render_target = _RenderTarget(scene, None)
    render_target.pipeline = _Pipeline("Pipe")

    inspector = RenderTargetInspectorTcgui(_TextureResourceManager())
    inspector.set_scene_getter(lambda: [scene])
    inspector.set_render_target(render_target, scene)

    assert len(inspector._pipeline_params_widgets) == 1
    assert inspector._pipeline_params_widgets[0]._preview is not None


def test_render_target_inspector_edits_attachment_formats():
    scene = _Scene("Scene", 1, [])
    render_target = _RenderTarget(scene, None)

    inspector = RenderTargetInspectorTcgui(_ResourceManager())
    inspector.set_scene_getter(lambda: [scene])
    inspector.set_render_target(render_target, scene)

    assert inspector._color_format.selected_index == 0
    assert inspector._depth_format.selected_index == 0

    inspector._on_color_format_changed(1, "RGBA8")
    inspector._on_depth_format_changed(1, "Depth 24")

    assert render_target.color_format == "rgba8"
    assert render_target.depth_format == "depth24"


def test_render_target_inspector_edits_clear_settings():
    scene = _Scene("Scene", 1, [])
    render_target = _RenderTarget(scene, None)

    inspector = RenderTargetInspectorTcgui(_ResourceManager())
    inspector.set_scene_getter(lambda: [scene])
    inspector.set_render_target(render_target, scene)

    inspector._on_clear_color_changed(True)
    inspector._clear_color_spins[0].value = 0.25
    inspector._clear_color_spins[1].value = 0.5
    inspector._clear_color_spins[2].value = 0.75
    inspector._clear_color_spins[3].value = 1.0
    inspector._on_clear_color_value_changed(0.25)
    inspector._on_clear_depth_changed(True)
    inspector._clear_depth_value.value = 0.5
    inspector._on_clear_depth_value_changed(0.5)

    assert render_target.clear_color_enabled is True
    assert render_target.clear_color_value == (0.25, 0.5, 0.75, 1.0)
    assert render_target.clear_depth_enabled is True
    assert render_target.clear_depth_value == 0.5


def test_texture_picker_with_scene_getter_includes_live_render_target_pool(monkeypatch):
    scene_mount_module = types.ModuleType("termin.visualization.core.scene")
    scene_mount_module.scene_render_mount = lambda scene: types.SimpleNamespace(render_target_configs=[])
    monkeypatch.setitem(sys.modules, "termin.visualization.core.scene", scene_mount_module)

    live_rt = types.SimpleNamespace(alive=True, name="LiveRT", index=1, generation=1)
    render_framework_module = types.ModuleType("termin.render_framework")
    render_framework_module.render_target_pool_list = lambda: [live_rt]
    monkeypatch.setitem(sys.modules, "termin.render_framework", render_framework_module)

    picker = TexturePickerWidget(
        _ResourceManager(),
        on_changed=lambda _tag, _value: None,
        scene_getter=lambda: [types.SimpleNamespace(name="Scene", uuid="scene")],
        show_preview=False,
    )
    picker.set_value("", "default")

    assert ("rt_color", "LiveRT") in zip(picker._item_tags, picker._item_values)
    assert ("rt_depth", "LiveRT") in zip(picker._item_tags, picker._item_values)


def test_texture_picker_lists_render_targets_before_file_textures(monkeypatch):
    scene_mount_module = types.ModuleType("termin.visualization.core.scene")
    scene_mount_module.scene_render_mount = lambda scene: types.SimpleNamespace(render_target_configs=[])
    monkeypatch.setitem(sys.modules, "termin.visualization.core.scene", scene_mount_module)

    live_rt = types.SimpleNamespace(alive=True, name="LiveRT", index=1, generation=1)
    render_framework_module = types.ModuleType("termin.render_framework")
    render_framework_module.render_target_pool_list = lambda: [live_rt]
    monkeypatch.setitem(sys.modules, "termin.render_framework", render_framework_module)

    class ResourceManagerWithTextures(_ResourceManager):
        def list_texture_names(self):
            return [f"Image{i}" for i in range(12)]

    picker = TexturePickerWidget(
        ResourceManagerWithTextures(),
        on_changed=lambda _tag, _value: None,
        scene_getter=lambda: [types.SimpleNamespace(name="Scene", uuid="scene")],
        show_preview=False,
    )
    picker.set_value("", "default")

    assert picker._item_tags[:4] == ["default", "rt_color", "rt_depth", "file"]
    assert picker._item_values[1:3] == ["LiveRT", "LiveRT"]


def test_render_target_inspector_saves_file_pipeline_param_by_uuid(monkeypatch):
    texture_module = types.ModuleType("termin.visualization.render.texture")
    texture_module.get_white_texture = lambda: types.SimpleNamespace(_image_data=None)
    texture_module.get_normal_texture = lambda: types.SimpleNamespace(_image_data=None)
    monkeypatch.setitem(sys.modules, "termin.visualization.render.texture", texture_module)

    scene_mount_module = types.ModuleType("termin.visualization.core.scene")
    scene_mount_module.scene_render_mount = lambda scene: types.SimpleNamespace(render_target_configs=[])
    monkeypatch.setitem(sys.modules, "termin.visualization.core.scene", scene_mount_module)

    scene = _Scene("Scene", 1, [])
    render_target = _RenderTarget(scene, None)
    render_target.pipeline = _Pipeline("Pipe")

    inspector = RenderTargetInspectorTcgui(_TextureResourceManager())
    inspector.set_scene_getter(lambda: [scene])
    inspector.set_render_target(render_target, scene)
    inspector._on_pipeline_param_changed("input_texture", "file", "Grenade")

    assert render_target.pipeline_params == {
        "input_texture": "file:texture-uuid-grenade",
    }


def test_render_target_inspector_reads_uuid_file_pipeline_param(monkeypatch):
    texture_module = types.ModuleType("termin.visualization.render.texture")
    texture_module.get_white_texture = lambda: types.SimpleNamespace(_image_data=None)
    texture_module.get_normal_texture = lambda: types.SimpleNamespace(_image_data=None)
    monkeypatch.setitem(sys.modules, "termin.visualization.render.texture", texture_module)

    scene_mount_module = types.ModuleType("termin.visualization.core.scene")
    scene_mount_module.scene_render_mount = lambda scene: types.SimpleNamespace(render_target_configs=[])
    monkeypatch.setitem(sys.modules, "termin.visualization.core.scene", scene_mount_module)

    scene = _Scene("Scene", 1, [])
    render_target = _RenderTarget(scene, None)
    render_target.pipeline = _Pipeline("Pipe")
    render_target.pipeline_params = {
        "input_texture": "file:texture-uuid-grenade",
    }

    inspector = RenderTargetInspectorTcgui(_TextureResourceManager())
    inspector.set_scene_getter(lambda: [scene])
    inspector.set_render_target(render_target, scene)

    picker = inspector._pipeline_params_widgets[0]
    assert picker._item_tags[picker._combo.selected_index] == "file"
    assert picker._item_values[picker._combo.selected_index] == "Grenade"
