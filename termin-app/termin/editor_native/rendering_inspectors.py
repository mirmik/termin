"""Native projections and switching host for rendering object inspectors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import logging
import weakref

from termin.editor_core.inspector_model import InspectorKind, InspectorModel
from termin.editor_core.rendering_inspector_models import (
    DisplayInspectorController,
    DisplayInspectorSnapshot,
    InspectorChoice,
    RenderTargetInspectorController,
    RenderTargetInspectorSnapshot,
    ViewportInspectorController,
    ViewportInspectorSnapshot,
)
from termin.gui_native import TcDocument, Size, WidgetRef
from termin.editor_native.metrics import EDITOR_UI_METRICS

from .inspector_fields import (
    ColorDialogHandler,
    LayerMaskDialogHandler,
    build_native_color_control,
)


_logger = logging.getLogger(__name__)


def _panel(document: TcDocument, stable_id: str) -> tuple[WidgetRef, WidgetRef]:
    root = document.create_vstack(f"{stable_id}-root")
    root.stable_id = stable_id
    content = document.create_vstack(f"{stable_id}-content")
    content.set_layout_padding(EDITOR_UI_METRICS.panel_insets)
    content.set_layout_spacing(EDITOR_UI_METRICS.spacing)
    scroll = document.create_scroll_area(f"{stable_id}-scroll")
    scroll.set_scroll_axes(False, True)
    scroll.set_content(content)
    root.add_stretch_child(scroll.widget)
    return root, content


def _clear(document: TcDocument, content: WidgetRef) -> None:
    for child in tuple(content.children):
        if not document.destroy_widget_recursive(child.handle):
            _logger.error("Failed to destroy rendering inspector row: %s", child.debug_name)


def _row(
    document: TcDocument,
    label: str,
    key: str,
    label_width: float = EDITOR_UI_METRICS.inspector_label,
) -> WidgetRef:
    row = document.create_hstack(f"rendering-inspector-row-{key}")
    row.set_layout_spacing(4.0)
    row.add_fixed_child(document.create_label(label, f"rendering-inspector-label-{key}"), label_width)
    return row


def _append_label(
    document: TcDocument,
    content: WidgetRef,
    label: str,
    value: str,
    key: str,
) -> object:
    row = _row(document, label, key)
    control = document.create_status_bar(value)
    row.add_stretch_child(control.widget)
    content.add_fixed_child(row, 28.0)
    return control


def _combo(document: TcDocument, choices: tuple[InspectorChoice, ...], selected: int):
    control = document.create_combo_box()
    for choice in choices:
        control.add_item(choice.label)
    control.selected_index = selected
    return control


@dataclass
class NativeDisplayInspector:
    document: TcDocument
    controller: DisplayInspectorController
    root: WidgetRef
    content: WidgetRef
    request_render: Callable[[], None]
    controls: dict[str, object] = field(default_factory=dict)

    def set_target(self, display) -> None:
        self.rebuild(self.controller.set_target(display))

    def rebuild(self, snapshot: DisplayInspectorSnapshot) -> None:
        _clear(self.document, self.content)
        self.controls.clear()
        self.content.add_fixed_child(self.document.create_label("Display Inspector"), 28.0)
        if not snapshot.has_display:
            self.content.add_fixed_child(self.document.create_label("No display selected."), 26.0)
            self.request_render()
            return
        self.content.add_fixed_child(self.document.create_label(snapshot.name or "Display"), 24.0)
        name_row = _row(self.document, "Name", "display-name")
        name = self.document.create_text_input(snapshot.name)
        name.connect_submitted(lambda value: self._mutate(lambda: self.controller.set_name(value)))
        name_row.add_stretch_child(name.widget)
        self.content.add_fixed_child(name_row, 30.0)
        self.controls["name"] = name
        self.controls["surface"] = _append_label(
            self.document, self.content, "Surface", snapshot.surface_type, "display-surface"
        )
        size = "—" if snapshot.size is None else f"{snapshot.size[0]} × {snapshot.size[1]}"
        self.controls["size"] = _append_label(
            self.document, self.content, "Size", size, "display-size"
        )
        self.controls["viewports"] = _append_label(
            self.document, self.content, "Viewports", str(snapshot.viewport_count), "display-viewports"
        )
        editor_row = _row(self.document, "Editor only", "display-editor-only")
        editor_only = self.document.create_checkbox(snapshot.editor_only)
        editor_only.connect_changed(
            lambda value: self._mutate(lambda: self.controller.set_editor_only(value))
        )
        editor_row.add_stretch_child(editor_only.widget)
        self.content.add_fixed_child(editor_row, 28.0)
        self.controls["editor_only"] = editor_only
        self.controls["identity"] = _append_label(
            self.document, self.content, "Identity", snapshot.debug_identity, "display-identity"
        )
        self.request_render()

    def _mutate(self, mutation) -> None:
        self.rebuild(mutation())


@dataclass
class NativeViewportInspector:
    document: TcDocument
    controller: ViewportInspectorController
    root: WidgetRef
    content: WidgetRef
    request_render: Callable[[], None]
    controls: dict[str, object] = field(default_factory=dict)

    def set_target(self, viewport) -> None:
        self.rebuild(self.controller.set_target(viewport))

    def rebuild(self, snapshot: ViewportInspectorSnapshot) -> None:
        _clear(self.document, self.content)
        self.controls.clear()
        self.content.add_fixed_child(self.document.create_label("Viewport Inspector"), 28.0)
        if not snapshot.has_viewport:
            self.content.add_fixed_child(self.document.create_label("No viewport selected."), 26.0)
            self.request_render()
            return
        self.content.add_fixed_child(self.document.create_label(snapshot.name), 24.0)
        self._append_checkbox("Enabled", "enabled", snapshot.enabled, self.controller.set_enabled)
        self._append_choice("Display", "display", snapshot.displays, snapshot.display_index,
                            self.controller.set_display)
        self.controls["display"].widget.enabled = snapshot.display_editable
        self._append_choice("Scene", "scene", snapshot.scenes, snapshot.scene_index,
                            self.controller.set_scene)
        mode_choices = tuple(InspectorChoice(mode, mode) for mode in snapshot.input_modes)
        self._append_choice("Input mode", "input-mode", mode_choices, snapshot.input_mode_index,
                            self.controller.set_input_mode)
        self._append_checkbox(
            "Block in editor",
            "block-input",
            snapshot.block_input_in_editor,
            self.controller.set_block_input_in_editor,
        )
        rect_row = _row(self.document, "Rect (0..1)", "viewport-rect")
        rect_boxes = []
        for value in snapshot.rect:
            box = self.document.create_spin_box(value)
            box.set_range(0.0, 1.0)
            box.step = 0.05
            box.decimals = 3
            rect_row.add_stretch_child(box.widget)
            rect_boxes.append(box)
        controls = tuple(rect_boxes)

        def rect_changed(_value: float) -> None:
            self._mutate(lambda: self.controller.set_rect(box.value for box in controls))

        for box in controls:
            box.connect_changed(rect_changed)
        self.content.add_fixed_child(rect_row, 30.0)
        self.controls["rect"] = controls
        depth_row = _row(self.document, "Depth", "viewport-depth")
        depth = self.document.create_spin_box(float(snapshot.depth))
        depth.set_range(-1000.0, 1000.0)
        depth.step = 1.0
        depth.decimals = 0
        depth.connect_changed(
            lambda value: self._mutate(lambda: self.controller.set_depth(int(value)))
        )
        depth_row.add_stretch_child(depth.widget)
        self.content.add_fixed_child(depth_row, 30.0)
        self.controls["depth"] = depth
        self._append_choice(
            "Render target",
            "render-target",
            snapshot.render_targets,
            snapshot.render_target_index,
            self.controller.set_render_target,
        )
        self.request_render()

    def _append_checkbox(self, label: str, key: str, value: bool, setter) -> None:
        row = _row(self.document, label, f"viewport-{key}")
        control = self.document.create_checkbox(value)
        control.connect_changed(lambda checked: self._mutate(lambda: setter(checked)))
        row.add_stretch_child(control.widget)
        self.content.add_fixed_child(row, 28.0)
        self.controls[key] = control

    def _append_choice(self, label: str, key: str, choices, selected: int, setter) -> None:
        row = _row(self.document, label, f"viewport-{key}")
        control = _combo(self.document, choices, selected)
        control.connect_changed(lambda index, _text: self._mutate(lambda: setter(index)))
        row.add_stretch_child(control.widget)
        self.content.add_fixed_child(row, 30.0)
        self.controls[key] = control

    def _mutate(self, mutation) -> None:
        self.rebuild(mutation())


@dataclass
class NativeRenderTargetInspector:
    document: TcDocument
    controller: RenderTargetInspectorController
    root: WidgetRef
    content: WidgetRef
    request_render: Callable[[], None]
    show_color_dialog: ColorDialogHandler | None = None
    show_layer_mask_dialog: LayerMaskDialogHandler | None = None
    controls: dict[str, object] = field(default_factory=dict)

    def set_target(self, render_target, fallback_scene=None) -> None:
        self.rebuild(self.controller.set_target(render_target, fallback_scene))

    def rebuild(self, snapshot: RenderTargetInspectorSnapshot) -> None:
        _clear(self.document, self.content)
        self.controls.clear()
        self.content.add_fixed_child(self.document.create_label("Render Target Inspector"), 28.0)
        if not snapshot.has_target:
            self.content.add_fixed_child(self.document.create_label("No render target selected."), 26.0)
            self.request_render()
            return
        self.content.add_fixed_child(self.document.create_label(snapshot.name), 24.0)
        self._append_checkbox("Enabled", "enabled", snapshot.enabled, self.controller.set_enabled)
        self._append_choice("Type", "kind", snapshot.kind_choices, snapshot.kind_index,
                            self.controller.set_kind)
        self._append_choice("Scene", "scene", snapshot.scenes, snapshot.scene_index,
                            self.controller.set_scene)
        self._append_choice(snapshot.source_label, "source", snapshot.sources, snapshot.source_index,
                            self.controller.set_source)
        self._append_choice("Pipeline", "pipeline", snapshot.pipelines, snapshot.pipeline_index,
                            self.controller.set_pipeline)
        if snapshot.is_texture_target:
            self._append_checkbox(
                "Use view size",
                "dynamic-resolution",
                snapshot.dynamic_resolution,
                self.controller.set_dynamic_resolution,
            )
            self._append_choice(
                "Color format", "color-format", snapshot.color_formats,
                snapshot.color_format_index, self.controller.set_color_format,
            )
            self._append_choice(
                "Depth format", "depth-format", snapshot.depth_formats,
                snapshot.depth_format_index, self.controller.set_depth_format,
            )
        self._append_checkbox(
            "Clear color", "clear-color-enabled", snapshot.clear_color_enabled,
            self.controller.set_clear_color_enabled,
        )
        self._append_color(snapshot)
        self._append_checkbox(
            "Clear depth", "clear-depth-enabled", snapshot.clear_depth_enabled,
            self.controller.set_clear_depth_enabled,
        )
        depth_row = _row(self.document, "Depth value", "target-clear-depth")
        depth = self.document.create_spin_box(snapshot.clear_depth_value)
        depth.set_range(0.0, 1.0)
        depth.step = 0.01
        depth.decimals = 4
        depth.connect_changed(
            lambda value: self._mutate(lambda: self.controller.set_clear_depth_value(value))
        )
        depth_row.add_stretch_child(depth.widget)
        self.content.add_fixed_child(depth_row, 30.0)
        self.controls["clear-depth-value"] = depth
        if snapshot.is_texture_target and not snapshot.dynamic_resolution:
            self._append_size(snapshot)
        self._append_layer_mask(snapshot)
        if snapshot.pipeline_parameters:
            self.content.add_fixed_child(self.document.create_label("Pipeline Parameters"), 26.0)
            for parameter in snapshot.pipeline_parameters:
                self._append_choice(
                    parameter.slot,
                    f"pipeline-param:{parameter.slot}",
                    parameter.choices,
                    parameter.selected_index,
                    lambda index, slot=parameter.slot: self.controller.set_pipeline_parameter(slot, index),
                )
        self.request_render()

    def _append_checkbox(self, label: str, key: str, value: bool, setter) -> None:
        row = _row(self.document, label, f"target-{key}")
        control = self.document.create_checkbox(value)
        control.connect_changed(lambda checked: self._mutate(lambda: setter(checked)))
        row.add_stretch_child(control.widget)
        self.content.add_fixed_child(row, 28.0)
        self.controls[key] = control

    def _append_choice(self, label: str, key: str, choices, selected: int, setter) -> None:
        row = _row(self.document, label, f"target-{key}")
        control = _combo(self.document, choices, selected)
        control.connect_changed(lambda index, _text: self._mutate(lambda: setter(index)))
        row.add_stretch_child(control.widget)
        self.content.add_fixed_child(row, 30.0)
        self.controls[key] = control

    def _append_color(self, snapshot: RenderTargetInspectorSnapshot) -> None:
        weak_owner = weakref.ref(self)

        def clicked() -> None:
            owner = weak_owner()
            if owner is None:
                return
            if owner.show_color_dialog is None:
                _logger.error("Render target inspector has no color dialog service")
                return

            def finished(value: tuple[float, ...] | None) -> None:
                current = weak_owner()
                if current is not None and value is not None:
                    current._mutate(lambda: current.controller.set_clear_color_value(value))

            owner.show_color_dialog(snapshot.clear_color_value, finished)

        row = _row(self.document, "Clear value", "target-clear-color-value")
        control, button = build_native_color_control(
            self.document,
            snapshot.clear_color_value,
            debug_name="native-render-target-clear-color",
            on_clicked=clicked,
        )
        row.add_stretch_child(control)
        self.content.add_fixed_child(row, 30.0)
        self.controls["clear-color-value"] = button

    def _append_size(self, snapshot: RenderTargetInspectorSnapshot) -> None:
        row = _row(self.document, "Size", "target-size")
        width = self.document.create_spin_box(float(snapshot.width))
        height = self.document.create_spin_box(float(snapshot.height))
        for box in (width, height):
            box.set_range(1.0, 8192.0)
            box.step = 64.0
            box.decimals = 0
            row.add_stretch_child(box.widget)
        controls = (width, height)

        def changed(_value: float) -> None:
            self._mutate(
                lambda: self.controller.set_size(int(controls[0].value), int(controls[1].value))
            )

        width.connect_changed(changed)
        height.connect_changed(changed)
        self.content.add_fixed_child(row, 30.0)
        self.controls["size"] = controls

    def _append_layer_mask(self, snapshot: RenderTargetInspectorSnapshot) -> None:
        row = _row(self.document, "Layer mask", "target-layer-mask")
        button = self.document.create_button(f"0x{snapshot.layer_mask:X}")
        weak_owner = weakref.ref(self)

        def clicked() -> None:
            owner = weak_owner()
            if owner is None:
                return
            if owner.show_layer_mask_dialog is None:
                _logger.error("Render target inspector has no layer-mask dialog service")
                return

            def finished(value: int | None) -> None:
                current = weak_owner()
                if current is not None and value is not None:
                    current._mutate(lambda: current.controller.set_layer_mask(value))

            owner.show_layer_mask_dialog(snapshot.layer_mask, snapshot.layer_names, finished)

        button.connect_clicked(clicked)
        row.add_stretch_child(button.widget)
        self.content.add_fixed_child(row, 30.0)
        self.controls["layer-mask"] = button

    def _mutate(self, mutation) -> None:
        self.rebuild(mutation())


@dataclass
class NativeInspectorHost:
    model: InspectorModel
    root: WidgetRef
    entity_inspector: object
    material_inspector: object
    texture_inspector: object
    mesh_inspector: object
    glb_inspector: object
    pipeline_inspector: object
    tool_inspector: object
    display_inspector: NativeDisplayInspector
    viewport_inspector: NativeViewportInspector
    render_target_inspector: NativeRenderTargetInspector

    def show_entity(self, target) -> None:
        self.model.resync_from_selection(target)

    def show_display(self, display, name: str = "") -> None:
        self.model.show_display(display, name)

    def show_viewport(self, viewport) -> None:
        self.model.show_viewport(viewport)

    def show_render_target(self, render_target) -> None:
        self.model.show_render_target(render_target)

    def register_tool_panel(self, key: str, panel: WidgetRef) -> None:
        self.tool_inspector.register(key, panel)

    def unregister_tool_panel(self, key: str) -> WidgetRef | None:
        return self.tool_inspector.unregister(key)

    def show_tool_panel(self, key: str, label: str = "") -> None:
        self.model.show_tool(key, label or key)

    def apply_model(self, model: InspectorModel) -> None:
        panels = (
            self.entity_inspector.root,
            self.material_inspector.root,
            self.texture_inspector.root,
            self.mesh_inspector.root,
            self.glb_inspector.root,
            self.pipeline_inspector.root,
            self.tool_inspector.root,
            self.display_inspector.root,
            self.viewport_inspector.root,
            self.render_target_inspector.root,
        )
        for panel in panels:
            panel.visible = False
        if model.kind is InspectorKind.ENTITY:
            self.entity_inspector.root.visible = True
            self.entity_inspector.set_target(model.target)
        elif model.kind is InspectorKind.MATERIAL:
            self.entity_inspector.set_target(None)
            self.material_inspector.root.visible = True
            self.material_inspector.set_target(model.target)
        elif model.kind is InspectorKind.TEXTURE:
            self.entity_inspector.set_target(None)
            self.texture_inspector.root.visible = True
            self.texture_inspector.set_target(
                model.target,
                name=model.label,
                file_path=model.extras.get("file_path"),
            )
        elif model.kind is InspectorKind.MESH:
            self.entity_inspector.set_target(None)
            self.mesh_inspector.root.visible = True
            self.mesh_inspector.set_target(
                model.target,
                name=model.label,
                file_path=model.extras.get("file_path"),
            )
        elif model.kind is InspectorKind.GLB:
            self.entity_inspector.set_target(None)
            self.glb_inspector.root.visible = True
            self.glb_inspector.set_target(
                model.target,
                name=model.label,
                file_path=model.extras.get("file_path"),
            )
        elif model.kind is InspectorKind.PIPELINE:
            self.entity_inspector.set_target(None)
            self.pipeline_inspector.root.visible = True
            self.pipeline_inspector.set_target(
                model.target,
                name=model.label,
                file_path=model.extras.get("file_path"),
            )
        elif model.kind is InspectorKind.TOOL:
            self.entity_inspector.set_target(None)
            self.tool_inspector.root.visible = True
            self.tool_inspector.set_target(model.target, label=model.label)
        elif model.kind is InspectorKind.DISPLAY:
            self.entity_inspector.set_target(None)
            self.display_inspector.root.visible = True
            self.display_inspector.set_target(model.target)
        elif model.kind is InspectorKind.VIEWPORT:
            self.entity_inspector.set_target(None)
            self.viewport_inspector.root.visible = True
            self.viewport_inspector.set_target(model.target)
        elif model.kind is InspectorKind.RENDER_TARGET:
            self.entity_inspector.set_target(None)
            self.render_target_inspector.root.visible = True
            self.render_target_inspector.set_target(model.target, model.scene)
        else:
            _logger.error("Native inspector host does not support inspector kind %s", model.kind.value)
            self.entity_inspector.root.visible = True
            self.entity_inspector.set_target(None)


def build_native_rendering_inspectors(
    document: TcDocument,
    *,
    model: InspectorModel,
    entity_inspector,
    material_inspector,
    texture_inspector,
    mesh_inspector,
    glb_inspector,
    pipeline_inspector,
    tool_inspector,
    display_controller: DisplayInspectorController,
    viewport_controller: ViewportInspectorController,
    render_target_controller: RenderTargetInspectorController,
    request_render: Callable[[], None],
    show_color_dialog: ColorDialogHandler | None = None,
    show_layer_mask_dialog: LayerMaskDialogHandler | None = None,
) -> NativeInspectorHost:
    root = document.create_vstack("native-inspector-host")
    root.stable_id = "editor.inspector.host"
    root.preferred_size = Size(360.0, 626.0)
    display_root, display_content = _panel(document, "editor.inspector.display")
    viewport_root, viewport_content = _panel(document, "editor.inspector.viewport")
    target_root, target_content = _panel(document, "editor.inspector.render-target")
    display = NativeDisplayInspector(
        document, display_controller, display_root, display_content, request_render
    )
    viewport = NativeViewportInspector(
        document, viewport_controller, viewport_root, viewport_content, request_render
    )
    target = NativeRenderTargetInspector(
        document,
        render_target_controller,
        target_root,
        target_content,
        request_render,
        show_color_dialog,
        show_layer_mask_dialog,
    )
    for panel in (
        entity_inspector.root,
        material_inspector.root,
        texture_inspector.root,
        mesh_inspector.root,
        glb_inspector.root,
        pipeline_inspector.root,
        tool_inspector.root,
        display_root,
        viewport_root,
        target_root,
    ):
        root.add_stretch_child(panel)
    result = NativeInspectorHost(
        model,
        root,
        entity_inspector,
        material_inspector,
        texture_inspector,
        mesh_inspector,
        glb_inspector,
        pipeline_inspector,
        tool_inspector,
        display,
        viewport,
        target,
    )
    weak_result = weakref.ref(result)

    def changed(current_model: InspectorModel) -> None:
        owner = weak_result()
        if owner is not None:
            owner.apply_model(current_model)
            request_render()

    model.changed.connect(changed)
    result.apply_model(model)
    return result


__all__ = [
    "NativeDisplayInspector",
    "NativeInspectorHost",
    "NativeRenderTargetInspector",
    "NativeViewportInspector",
    "build_native_rendering_inspectors",
]
