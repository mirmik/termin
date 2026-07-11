import sys
import types

from termin.editor_core.rendering_inspector_models import (
    DisplayInspectorController,
    RenderTargetInspectorController,
    ViewportInspectorController,
)


class _SceneHandle:
    def __init__(self, index, generation=1):
        self.index = index
        self.generation = generation


class _Entity:
    def __init__(self, name, component=None):
        self.name = name
        self.uuid = name
        self.component = component

    def get_component(self, component_type):
        return self.component if isinstance(self.component, component_type) else None


class _Scene:
    def __init__(self, name, index, entities=()):
        self.name = name
        self.entities = list(entities)
        self._handle = _SceneHandle(index)

    def scene_handle(self):
        return self._handle


class _Surface:
    pass


class _Display:
    def __init__(self, name, pointer):
        self.name = name
        self.tc_display_ptr = pointer
        self.surface = _Surface()
        self.viewports = []
        self.editor_only = False

    def get_size(self):
        return 1280, 720


class _Viewport:
    def __init__(self, scene, render_target):
        self.name = "Main"
        self.enabled = True
        self.scene = scene
        self.input_mode = "simple"
        self.block_input_in_editor = False
        self.rect = (0.0, 0.0, 1.0, 1.0)
        self.depth = 2
        self.render_target = render_target


class _Camera:
    pass


class _Pipeline:
    def __init__(self, name):
        self.name = name


class _PipelineAsset:
    external_params = ("source",)


class _TextureAsset:
    def __init__(self, name, uuid):
        self.name = name
        self.uuid = uuid


class _ResourceManager:
    def __init__(self):
        self.pipeline = _Pipeline("Post")
        self.texture = _TextureAsset("Noise", "texture-noise")

    def list_pipeline_names(self):
        return ["Post"]

    def get_pipeline(self, name):
        return self.pipeline if name == "Post" else None

    def get_pipeline_asset(self, name):
        return _PipelineAsset() if name == "Post" else None

    def get_scene_pipeline_asset(self, _name):
        return None

    def list_texture_names(self):
        return ["Noise"]

    def get_texture_asset(self, name):
        return self.texture if name == "Noise" else None

    def get_texture_asset_by_uuid(self, uuid):
        return self.texture if uuid == self.texture.uuid else None


class _RenderTarget:
    def __init__(self, scene, camera, pipeline):
        self.name = "Target"
        self.index = 7
        self.generation = 3
        self.kind = "texture_2d"
        self.enabled = True
        self.scene = scene
        self.camera = camera
        self.xr_origin = None
        self.pipeline = pipeline
        self.dynamic_resolution = True
        self.color_format = "rgba16f"
        self.depth_format = "depth32f"
        self.clear_color_enabled = False
        self.clear_color_value = (0.0, 0.0, 0.0, 1.0)
        self.clear_depth_enabled = False
        self.clear_depth_value = 1.0
        self.width = 640
        self.height = 360
        self.layer_mask = 0xFF
        self.pipeline_params = {}


def test_display_inspector_snapshot_and_edits():
    changed = []
    display = _Display("Game", 123)
    controller = DisplayInspectorController(changed=lambda: changed.append(True))

    snapshot = controller.set_target(display)

    assert snapshot.name == "Game"
    assert snapshot.surface_type == "_Surface"
    assert snapshot.size == (1280, 720)
    assert snapshot.debug_identity == "0x7B"

    controller.set_name("Preview")
    controller.set_editor_only(True)

    assert display.name == "Preview"
    assert display.editor_only is True
    assert len(changed) == 2


def test_viewport_inspector_snapshot_and_mutations():
    first_scene = _Scene("Scene A", 1)
    second_scene = _Scene("Scene B", 2)
    first_target = types.SimpleNamespace(name="A", index=1, generation=1)
    second_target = types.SimpleNamespace(name="B", index=2, generation=1)
    first_display = _Display("Display A", 10)
    second_display = _Display("Display B", 20)
    viewport = _Viewport(first_scene, first_target)
    first_display.viewports.append(viewport)
    moves = []
    owner = [first_display]
    controller = ViewportInspectorController(
        displays=lambda _viewport: (first_display, second_display),
        scenes=lambda: (first_scene, second_scene),
        render_targets=lambda: (first_target, second_target),
        owner_display=lambda _viewport: owner[0],
        move_viewport=lambda vp, source, target: (moves.append((vp, source, target)), owner.__setitem__(0, target)),
        can_move_viewport=lambda _viewport: True,
    )

    snapshot = controller.set_target(viewport)

    assert snapshot.display_index == 0
    assert snapshot.scene_index == 0
    assert snapshot.input_mode_index == 1
    assert snapshot.render_target_index == 1

    controller.set_display(1)
    controller.set_scene(1)
    controller.set_input_mode(2)
    controller.set_block_input_in_editor(True)
    controller.set_rect((0.1, 0.2, 0.7, 0.8))
    controller.set_depth(5)
    controller.set_render_target(2)

    assert moves == [(viewport, first_display, second_display)]
    assert viewport.scene is second_scene
    assert viewport.input_mode == "editor"
    assert viewport.block_input_in_editor is True
    assert viewport.rect == (0.1, 0.2, 0.7, 0.8)
    assert viewport.depth == 5
    assert viewport.render_target is second_target


def test_render_target_inspector_snapshot_and_mutations(monkeypatch):
    camera_module = types.ModuleType("termin.render_components.camera")
    camera_module.CameraComponent = _Camera
    monkeypatch.setitem(sys.modules, "termin.render_components.camera", camera_module)
    camera = _Camera()
    scene = _Scene("Scene", 1, (_Entity("Camera", camera),))
    resources = _ResourceManager()
    target = _RenderTarget(scene, camera, resources.pipeline)
    defaults = []
    controller = RenderTargetInspectorController(
        resources,
        scenes=lambda: (scene,),
        layer_names=lambda: tuple(f"Layer {index}" for index in range(64)),
        create_default_pipeline=lambda: defaults.append(True) or _Pipeline("Default"),
    )

    snapshot = controller.set_target(target, scene)

    assert snapshot.scene_index == 1
    assert snapshot.source_index == 1
    assert snapshot.pipeline_index == 2
    assert snapshot.pipeline_parameters[0].slot == "source"

    controller.set_dynamic_resolution(False)
    controller.set_color_format(1)
    controller.set_depth_format(1)
    controller.set_clear_color_enabled(True)
    controller.set_clear_color_value((0.1, 0.2, 0.3, 1.0))
    controller.set_clear_depth_enabled(True)
    controller.set_clear_depth_value(0.5)
    controller.set_size(800, 600)
    controller.set_layer_mask(0x0F)
    file_index = next(
        index
        for index, choice in enumerate(controller.snapshot.pipeline_parameters[0].choices)
        if choice.value == ("file", "Noise")
    )
    controller.set_pipeline_parameter("source", file_index)
    controller.set_pipeline(1)

    assert target.dynamic_resolution is False
    assert target.color_format == "rgba8"
    assert target.depth_format == "depth24"
    assert target.clear_color_enabled is True
    assert target.clear_color_value == (0.1, 0.2, 0.3, 1.0)
    assert target.clear_depth_enabled is True
    assert target.clear_depth_value == 0.5
    assert (target.width, target.height) == (800, 600)
    assert target.layer_mask == 0x0F
    assert target.pipeline_params == {"source": "file:texture-noise"}
    assert target.pipeline.name == "Default"
    assert defaults == [True]
