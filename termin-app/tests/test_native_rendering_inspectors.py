import gc
from types import SimpleNamespace

from termin.editor_core.inspector_model import InspectorModel
from termin.editor_core.rendering_inspector_models import (
    DisplayInspectorSnapshot,
    InspectorChoice,
    RenderTargetInspectorSnapshot,
    ViewportInspectorSnapshot,
)
from termin.editor_native.rendering_inspectors import build_native_rendering_inspectors
from termin.gui_native import Document


class _EntityInspector:
    def __init__(self, document):
        self.root = document.create_vstack("entity-inspector-probe")
        self.targets = []

    def set_target(self, target):
        self.targets.append(target)


class _DisplayController:
    def set_target(self, display):
        return DisplayInspectorSnapshot(
            display=display,
            name=display.name,
            surface_type="Surface",
            size=(1280, 720),
            viewport_count=1,
            editor_only=False,
            debug_identity="0x1",
        )

    def set_name(self, _value):
        raise AssertionError("not exercised")

    def set_editor_only(self, _value):
        raise AssertionError("not exercised")


class _ViewportController:
    def set_target(self, viewport):
        return ViewportInspectorSnapshot(
            viewport=viewport,
            name=viewport.name,
            enabled=True,
            displays=(InspectorChoice("Editor", object()),),
            display_index=0,
            scenes=(InspectorChoice("Scene", object()),),
            scene_index=0,
            render_targets=(InspectorChoice("(None)", None),),
            render_target_index=0,
        )

    @staticmethod
    def _unexpected(*_args):
        raise AssertionError("not exercised")

    set_enabled = _unexpected
    set_display = _unexpected
    set_scene = _unexpected
    set_input_mode = _unexpected
    set_block_input_in_editor = _unexpected
    set_rect = _unexpected
    set_depth = _unexpected
    set_render_target = _unexpected


class _RenderTargetController:
    def set_target(self, target, _fallback_scene=None):
        return RenderTargetInspectorSnapshot(
            render_target=target,
            name=target.name,
            enabled=True,
            scenes=(InspectorChoice("(None)", None),),
            sources=(InspectorChoice("(None)", None),),
            pipelines=(InspectorChoice("(None)", None),),
            layer_names=tuple(f"Layer {index}" for index in range(64)),
        )

    @staticmethod
    def _unexpected(*_args):
        raise AssertionError("not exercised")

    set_enabled = _unexpected
    set_kind = _unexpected
    set_scene = _unexpected
    set_source = _unexpected
    set_pipeline = _unexpected
    set_dynamic_resolution = _unexpected
    set_color_format = _unexpected
    set_depth_format = _unexpected
    set_clear_color_enabled = _unexpected
    set_clear_color_value = _unexpected
    set_clear_depth_enabled = _unexpected
    set_clear_depth_value = _unexpected
    set_size = _unexpected
    set_layer_mask = _unexpected
    set_pipeline_parameter = _unexpected


def test_native_inspector_host_switches_rendering_object_panels():
    document = Document()
    model = InspectorModel(SimpleNamespace())
    entity = _EntityInspector(document)
    renders = []
    host = build_native_rendering_inspectors(
        document,
        model=model,
        entity_inspector=entity,
        display_controller=_DisplayController(),
        viewport_controller=_ViewportController(),
        render_target_controller=_RenderTargetController(),
        request_render=lambda: renders.append(True),
    )
    assert document.add_root(host.root.handle)

    display = SimpleNamespace(name="Editor")
    viewport = SimpleNamespace(name="Main")
    target = SimpleNamespace(name="ColorTarget")

    model.show_display(display, display.name)
    assert host.display_inspector.root.visible
    assert not entity.root.visible
    assert host.display_inspector.controls["name"].text == "Editor"

    model.show_viewport(viewport)
    assert host.viewport_inspector.root.visible
    assert not host.display_inspector.root.visible
    assert "render-target" in host.viewport_inspector.controls

    model.show_render_target(target)
    assert host.render_target_inspector.root.visible
    assert not host.viewport_inspector.root.visible
    assert "pipeline" in host.render_target_inspector.controls
    assert entity.targets[-1] is None
    assert renders

    assert document.destroy_widget_recursive(host.root.handle)
    del host
    del entity
    del model
    del document
    gc.collect()
