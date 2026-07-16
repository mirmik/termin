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


class _RenderingManager:
    def create_pipeline(self, name):
        return _Pipeline(name)


class _CameraComponent:
    pass


class _XrOriginComponent:
    pass


class _Entity:
    def __init__(self, name, camera=None, xr_origin=None):
        self.name = name
        self.uuid = name
        self._camera = camera
        self._xr_origin = xr_origin

    def get_component(self, component_type):
        if component_type is _CameraComponent:
            return self._camera
        if component_type is _XrOriginComponent:
            return self._xr_origin
        raise AssertionError(component_type)


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
        self.kind = "texture_2d"
        self.enabled = True
        self.locked = False
        self.scene = scene
        self.camera = camera
        self.xr_origin = None
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


class _FakeUi:
    def __init__(self):
        self.layout_requests = 0

    def request_layout(self):
        self.layout_requests += 1


def _install_camera_component_stub(monkeypatch):
    camera_module = types.ModuleType("termin.render_components.camera")
    camera_module.CameraComponent = _CameraComponent
    monkeypatch.setitem(sys.modules, "termin.render_components.camera", camera_module)


def _install_xr_origin_component_stub(monkeypatch):
    render_components_module = types.ModuleType("termin.render_components")
    render_components_module.XrOriginComponent = _XrOriginComponent
    monkeypatch.setitem(sys.modules, "termin.render_components", render_components_module)


def test_render_target_inspector_reads_camera_from_render_target_scene(monkeypatch):
    _install_camera_component_stub(monkeypatch)

    editor_camera = _CameraComponent()
    game_camera = _CameraComponent()
    editor_scene = _Scene("Editor", 1, [_Entity("EditorCamera", editor_camera)])
    game_scene = _Scene("Editor(game)", 2, [_Entity("GameCamera", game_camera)])
    render_target = _RenderTarget(game_scene, game_camera)

    inspector = RenderTargetInspectorTcgui(_ResourceManager(), _RenderingManager())
    inspector.set_scene_getter(lambda: [editor_scene, game_scene])
    inspector.set_render_target(render_target, editor_scene)

    assert inspector._scene is game_scene
    assert inspector._cameras == [game_camera]
    assert inspector._camera_combo.selected_index == 1


def test_render_target_inspector_pipeline_params_use_texture_preview(monkeypatch):
    texture_module = types.ModuleType("termin.render.texture")
    texture_module.get_white_texture = lambda: types.SimpleNamespace(_image_data=None)
    texture_module.get_normal_texture = lambda: types.SimpleNamespace(_image_data=None)
    monkeypatch.setitem(sys.modules, "termin.render.texture", texture_module)

    scene_mount_module = types.ModuleType("termin.render")
    scene_mount_module.scene_render_mount = lambda scene: types.SimpleNamespace(render_target_configs=[])
    monkeypatch.setitem(sys.modules, "termin.render", scene_mount_module)

    scene = _Scene("Scene", 1, [])
    render_target = _RenderTarget(scene, None)
    render_target.pipeline = _Pipeline("Pipe")

    inspector = RenderTargetInspectorTcgui(_TextureResourceManager(), _RenderingManager())
    inspector.set_scene_getter(lambda: [scene])
    inspector.set_render_target(render_target, scene)

    assert len(inspector._pipeline_params_widgets) == 1
    assert inspector._pipeline_params_widgets[0]._preview is not None


def test_render_target_inspector_edits_attachment_formats():
    scene = _Scene("Scene", 1, [])
    render_target = _RenderTarget(scene, None)

    inspector = RenderTargetInspectorTcgui(_ResourceManager(), _RenderingManager())
    inspector.set_scene_getter(lambda: [scene])
    inspector.set_render_target(render_target, scene)

    assert inspector._color_format.selected_index == 0
    assert inspector._depth_format.selected_index == 0
    assert "R16F" in inspector._color_format.items
    assert "R32F" in inspector._color_format.items

    inspector._on_color_format_changed(1, "RGBA8")
    inspector._on_depth_format_changed(1, "Depth 24")

    assert render_target.color_format == "rgba8"
    assert render_target.depth_format == "depth24"

    inspector._on_color_format_changed(inspector._color_format.items.index("R16F"), "R16F")
    assert render_target.color_format == "r16f"

    inspector._on_color_format_changed(inspector._color_format.items.index("R32F"), "R32F")
    assert render_target.color_format == "r32f"


def test_render_target_inspector_edits_clear_settings():
    scene = _Scene("Scene", 1, [])
    render_target = _RenderTarget(scene, None)

    inspector = RenderTargetInspectorTcgui(_ResourceManager(), _RenderingManager())
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


def test_render_target_inspector_requests_layout_when_manual_size_visibility_changes():
    scene = _Scene("Scene", 1, [])
    render_target = _RenderTarget(scene, None)

    inspector = RenderTargetInspectorTcgui(_ResourceManager(), _RenderingManager())
    fake_ui = _FakeUi()
    inspector._ui = fake_ui
    inspector.set_scene_getter(lambda: [scene])
    inspector.set_render_target(render_target, scene)

    before = fake_ui.layout_requests
    inspector._dynamic_resolution.checked = False
    inspector._on_dynamic_resolution_changed(False)

    assert render_target.dynamic_resolution is False
    assert inspector._width.visible is True
    assert inspector._height.visible is True
    assert fake_ui.layout_requests > before


def test_render_target_inspector_hides_texture_fields_for_xr_target(monkeypatch):
    _install_xr_origin_component_stub(monkeypatch)

    xr_origin = _XrOriginComponent()
    scene = _Scene("Scene", 1, [_Entity("PlayerOrigin", xr_origin=xr_origin)])
    render_target = _RenderTarget(scene, None)
    render_target.kind = "xr_stereo"
    render_target.xr_origin = xr_origin

    inspector = RenderTargetInspectorTcgui(_ResourceManager(), _RenderingManager())
    inspector.set_scene_getter(lambda: [scene])
    inspector.set_render_target(render_target, scene)

    assert inspector._kind_combo.selected_index == 1
    assert inspector._camera_lbl.text == "XR Origin:"
    assert inspector._camera_combo.visible is True
    assert inspector._camera_combo.selected_index == 1
    assert inspector._dynamic_resolution.visible is False
    assert inspector._color_format.visible is False
    assert inspector._depth_format.visible is False
    assert inspector._width.visible is False
    assert inspector._height.visible is False
    assert inspector._pipeline_combo.visible is True
    assert inspector._layer_mask_widget.visible is True


def test_render_target_inspector_uses_xr_origin_when_switching_to_xr_target(monkeypatch):
    _install_camera_component_stub(monkeypatch)
    _install_xr_origin_component_stub(monkeypatch)

    camera = _CameraComponent()
    xr_origin = _XrOriginComponent()
    scene = _Scene("Scene", 1, [
        _Entity("Camera", camera=camera),
        _Entity("PlayerOrigin", xr_origin=xr_origin),
    ])
    render_target = _RenderTarget(scene, camera)
    render_target.xr_origin = xr_origin

    inspector = RenderTargetInspectorTcgui(_ResourceManager(), _RenderingManager())
    inspector.set_scene_getter(lambda: [scene])
    inspector.set_render_target(render_target, scene)
    inspector._on_kind_changed(1, "XR Stereo")

    assert render_target.kind == "xr_stereo"
    assert render_target.camera is camera
    assert render_target.xr_origin is xr_origin
    assert inspector._camera_lbl.text == "XR Origin:"
    assert inspector._camera_combo.visible is True
    assert inspector._camera_combo.selected_index == 1


def test_texture_picker_with_scene_getter_includes_live_render_target_pool(monkeypatch):
    scene_mount_module = types.ModuleType("termin.render")
    scene_mount_module.scene_render_mount = lambda scene: types.SimpleNamespace(render_target_configs=[])
    monkeypatch.setitem(sys.modules, "termin.render", scene_mount_module)

    live_rt = types.SimpleNamespace(alive=True, name="LiveRT", kind="texture_2d", index=1, generation=1)
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

    assert ("rt_color", "LiveRT") in zip(picker._item_tags, picker._item_values, strict=True)
    assert ("rt_depth", "LiveRT") in zip(picker._item_tags, picker._item_values, strict=True)


def test_texture_picker_lists_render_targets_before_file_textures(monkeypatch):
    scene_mount_module = types.ModuleType("termin.render")
    scene_mount_module.scene_render_mount = lambda scene: types.SimpleNamespace(render_target_configs=[])
    monkeypatch.setitem(sys.modules, "termin.render", scene_mount_module)

    live_rt = types.SimpleNamespace(alive=True, name="LiveRT", kind="texture_2d", index=1, generation=1)
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


def test_texture_picker_skips_xr_render_targets(monkeypatch):
    scene_mount_module = types.ModuleType("termin.render")
    scene_mount_module.scene_render_mount = lambda scene: types.SimpleNamespace(render_target_configs=[])
    monkeypatch.setitem(sys.modules, "termin.render", scene_mount_module)

    xr_rt = types.SimpleNamespace(alive=True, name="XrRT", kind="xr_stereo", index=1, generation=1)
    render_framework_module = types.ModuleType("termin.render_framework")
    render_framework_module.render_target_pool_list = lambda: [xr_rt]
    monkeypatch.setitem(sys.modules, "termin.render_framework", render_framework_module)

    picker = TexturePickerWidget(
        _ResourceManager(),
        on_changed=lambda _tag, _value: None,
        scene_getter=lambda: [types.SimpleNamespace(name="Scene", uuid="scene")],
        show_preview=False,
    )
    picker.set_value("", "default")

    assert "XrRT" not in picker._item_values


def test_render_target_inspector_saves_file_pipeline_param_by_uuid(monkeypatch):
    texture_module = types.ModuleType("termin.render.texture")
    texture_module.get_white_texture = lambda: types.SimpleNamespace(_image_data=None)
    texture_module.get_normal_texture = lambda: types.SimpleNamespace(_image_data=None)
    monkeypatch.setitem(sys.modules, "termin.render.texture", texture_module)

    scene_mount_module = types.ModuleType("termin.render")
    scene_mount_module.scene_render_mount = lambda scene: types.SimpleNamespace(render_target_configs=[])
    monkeypatch.setitem(sys.modules, "termin.render", scene_mount_module)

    scene = _Scene("Scene", 1, [])
    render_target = _RenderTarget(scene, None)
    render_target.pipeline = _Pipeline("Pipe")

    inspector = RenderTargetInspectorTcgui(_TextureResourceManager(), _RenderingManager())
    inspector.set_scene_getter(lambda: [scene])
    inspector.set_render_target(render_target, scene)
    inspector._on_pipeline_param_changed("input_texture", "file", "Grenade")

    assert render_target.pipeline_params == {
        "input_texture": "file:texture-uuid-grenade",
    }


def test_render_target_inspector_rejects_unknown_file_pipeline_param(monkeypatch):
    texture_module = types.ModuleType("termin.render.texture")
    texture_module.get_white_texture = lambda: types.SimpleNamespace(_image_data=None)
    texture_module.get_normal_texture = lambda: types.SimpleNamespace(_image_data=None)
    monkeypatch.setitem(sys.modules, "termin.render.texture", texture_module)

    scene_mount_module = types.ModuleType("termin.render")
    scene_mount_module.scene_render_mount = lambda scene: types.SimpleNamespace(render_target_configs=[])
    monkeypatch.setitem(sys.modules, "termin.render", scene_mount_module)

    scene = _Scene("Scene", 1, [])
    render_target = _RenderTarget(scene, None)
    render_target.pipeline = _Pipeline("Pipe")
    render_target.pipeline_params = {"input_texture": "file:texture-uuid-grenade"}

    inspector = RenderTargetInspectorTcgui(_TextureResourceManager(), _RenderingManager())
    inspector.set_scene_getter(lambda: [scene])
    inspector.set_render_target(render_target, scene)
    inspector._on_pipeline_param_changed("input_texture", "file", "MissingTexture")

    assert render_target.pipeline_params == {}


def test_render_target_inspector_reads_uuid_file_pipeline_param(monkeypatch):
    texture_module = types.ModuleType("termin.render.texture")
    texture_module.get_white_texture = lambda: types.SimpleNamespace(_image_data=None)
    texture_module.get_normal_texture = lambda: types.SimpleNamespace(_image_data=None)
    monkeypatch.setitem(sys.modules, "termin.render.texture", texture_module)

    scene_mount_module = types.ModuleType("termin.render")
    scene_mount_module.scene_render_mount = lambda scene: types.SimpleNamespace(render_target_configs=[])
    monkeypatch.setitem(sys.modules, "termin.render", scene_mount_module)

    scene = _Scene("Scene", 1, [])
    render_target = _RenderTarget(scene, None)
    render_target.pipeline = _Pipeline("Pipe")
    render_target.pipeline_params = {
        "input_texture": "file:texture-uuid-grenade",
    }

    inspector = RenderTargetInspectorTcgui(_TextureResourceManager(), _RenderingManager())
    inspector.set_scene_getter(lambda: [scene])
    inspector.set_render_target(render_target, scene)

    picker = inspector._pipeline_params_widgets[0]
    assert picker._item_tags[picker._combo.selected_index] == "file"
    assert picker._item_values[picker._combo.selected_index] == "Grenade"
