"""InspectorController for tcgui — manages inspector panel switching.

State (which inspector kind is active, what the target is) lives in
:class:`termin.editor_core.inspector_model.InspectorModel`. The controller
owns the panels and reacts to model changes by toggling widget visibility.
"""

from __future__ import annotations

from typing import Any, Callable, List, Optional

from tcgui.widgets.vstack import VStack
from tcgui.widgets.widget import Widget

from termin.editor_core.inspector_model import InspectorKind, InspectorModel
from termin.editor_tcgui.display_inspector import DisplayInspectorTcgui
from termin.editor_tcgui.entity_inspector import EntityInspector
from termin.editor_tcgui.glb_inspector import GLBInspectorTcgui
from termin.editor_tcgui.material_inspector import MaterialInspectorTcgui
from termin.editor_tcgui.mesh_inspector import MeshInspectorTcgui
from termin.editor_tcgui.pipeline_inspector import PipelineInspectorTcgui
from termin.editor_tcgui.render_target_inspector import RenderTargetInspectorTcgui
from termin.editor_tcgui.texture_inspector import TextureInspectorTcgui
from termin.editor_tcgui.viewport_inspector import ViewportInspectorTcgui


class InspectorControllerTcgui:
    """Manages inspector panels for the tcgui editor.

    Panels live as children of the container VStack; only the active one
    has ``visible = True``. Selection routing and resource resolution are
    delegated to :class:`InspectorModel`.
    """

    def __init__(
        self,
        container: VStack,
        resource_manager,
        push_undo_command: Callable,
        on_transform_changed: Callable,
        on_component_changed: Callable,
        on_material_changed: Optional[Callable] = None,
        on_display_changed: Optional[Callable] = None,
        on_viewport_changed: Optional[Callable] = None,
        on_pipeline_changed: Optional[Callable] = None,
        dialog_service=None,
    ) -> None:
        self._resource_manager = resource_manager
        self._push_undo_command = push_undo_command
        self._container = container
        self._on_material_changed = on_material_changed
        self._on_display_changed = on_display_changed
        self._on_viewport_changed = on_viewport_changed
        self._on_pipeline_changed = on_pipeline_changed

        self._model = InspectorModel(resource_manager)

        self._entity_inspector = EntityInspector(resource_manager)
        self._entity_inspector.set_undo_command_handler(push_undo_command)
        self._entity_inspector.on_transform_changed = on_transform_changed
        self._entity_inspector.on_component_changed = on_component_changed
        container.add_child(self._entity_inspector)

        self._material_inspector = MaterialInspectorTcgui(resource_manager)
        self._display_inspector = DisplayInspectorTcgui()
        self._viewport_inspector = ViewportInspectorTcgui(resource_manager)
        self._pipeline_inspector = PipelineInspectorTcgui(resource_manager, dialog_service=dialog_service)
        self._texture_inspector = TextureInspectorTcgui(resource_manager)
        self._mesh_inspector = MeshInspectorTcgui(resource_manager)
        self._glb_inspector = GLBInspectorTcgui(resource_manager)
        self._render_target_inspector = RenderTargetInspectorTcgui(resource_manager)

        self._material_inspector.on_changed = self._emit_material_changed
        self._display_inspector.on_changed = self._emit_display_changed
        self._viewport_inspector.on_changed = self._emit_viewport_changed
        self._pipeline_inspector.on_changed = self._emit_pipeline_changed

        self._panel_by_kind: dict[InspectorKind, Widget] = {
            InspectorKind.ENTITY: self._entity_inspector,
            InspectorKind.MATERIAL: self._material_inspector,
            InspectorKind.DISPLAY: self._display_inspector,
            InspectorKind.VIEWPORT: self._viewport_inspector,
            InspectorKind.PIPELINE: self._pipeline_inspector,
            InspectorKind.TEXTURE: self._texture_inspector,
            InspectorKind.MESH: self._mesh_inspector,
            InspectorKind.GLB: self._glb_inspector,
            InspectorKind.RENDER_TARGET: self._render_target_inspector,
        }

        for kind, panel in self._panel_by_kind.items():
            if kind is InspectorKind.ENTITY:
                continue
            panel.visible = False
            container.add_child(panel)

        self._active_panel: Widget = self._entity_inspector

        self._model.changed.connect(self._on_model_changed)

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    @property
    def entity_inspector(self) -> EntityInspector:
        return self._entity_inspector

    @property
    def render_target_inspector(self) -> RenderTargetInspectorTcgui:
        return self._render_target_inspector

    @property
    def model(self) -> InspectorModel:
        return self._model

    # ------------------------------------------------------------------
    # External API — thin wrappers around InspectorModel
    # ------------------------------------------------------------------

    def set_scene(self, scene) -> None:
        self._model.set_scene(scene)
        self._entity_inspector.set_scene(scene)
        self._viewport_inspector.set_scene(scene)
        self._render_target_inspector.set_scene(scene)

    def set_render_target_scene_getter(self, getter: Callable[[], list]) -> None:
        self._render_target_inspector.set_scene_getter(getter)
        self._viewport_inspector.set_scene_getter(getter)

    def show_entity_inspector(self, entity=None) -> None:
        self._model.show_entity(entity)

    def show_material_inspector(self, material_name: str | None = None) -> None:
        self._model.show_material(material_name)

    def show_material_inspector_for_file(self, file_path: str) -> None:
        self._model.show_material_for_file(file_path)

    def show_display_inspector(self, display=None, name: str = "") -> None:
        self._model.show_display(display, name)

    def show_viewport_inspector(
        self,
        viewport=None,
        displays: Optional[List] = None,
        display_names: Optional[dict] = None,
        scene=None,
        current_display=None,
    ) -> None:
        if scene is not None and scene is not self._model.scene:
            self._model.set_scene(scene)
        self._model.show_viewport(
            viewport,
            displays=displays,
            display_names=display_names,
            current_display=current_display,
        )

    def show_render_target_inspector(self, render_target=None, scene=None) -> None:
        if scene is not None and scene is not self._model.scene:
            self._model.set_scene(scene)
        self._model.show_render_target(render_target)

    def show_pipeline_inspector_for_file(self, file_path: str) -> None:
        self._model.show_pipeline_for_file(file_path)

    def show_texture_inspector(self, texture_name: str | None = None) -> None:
        self._model.show_texture(texture_name)

    def show_texture_inspector_for_file(self, file_path: str) -> None:
        self._model.show_texture_for_file(file_path)

    def show_mesh_inspector(self, mesh_name: str | None = None) -> None:
        self._model.show_mesh(mesh_name)

    def show_mesh_inspector_for_file(self, file_path: str) -> None:
        self._model.show_mesh_for_file(file_path)

    def show_glb_inspector_for_file(self, file_path: str) -> None:
        self._model.show_glb_for_file(file_path)

    def set_entity_target(self, target: Any) -> None:
        self._model.request(InspectorKind.ENTITY, target=target, label="")

    def clear(self) -> None:
        self._model.clear()

    def resync_from_tree_selection(self, node_data) -> None:
        self._model.resync_from_selection(node_data)

    # ------------------------------------------------------------------
    # Model → view
    # ------------------------------------------------------------------

    def _show_panel(self, panel: Widget) -> None:
        if self._active_panel is panel:
            return
        for p in self._panel_by_kind.values():
            p.visible = (p is panel)
        self._active_panel = panel
        if self._container._ui is not None:
            self._container._ui.request_layout()

    def _on_model_changed(self, model: InspectorModel) -> None:
        kind = model.kind
        panel = self._panel_by_kind[kind]

        file_path = model.extras.get("file_path")

        if kind is InspectorKind.ENTITY:
            self._entity_inspector.set_target(model.target)

        elif kind is InspectorKind.MATERIAL:
            if file_path is not None:
                self._material_inspector.set_target(model.target, f"File: {file_path}")
            elif model.target is None:
                self._material_inspector.set_target(None, "No material selected.")
            else:
                self._material_inspector.set_target(model.target, f"Material: {model.label}")

        elif kind is InspectorKind.DISPLAY:
            self._display_inspector.set_display(model.target, model.label)

        elif kind is InspectorKind.VIEWPORT:
            displays = model.extras.get("displays")
            display_names = model.extras.get("display_names")
            if displays is not None:
                self._viewport_inspector.set_displays(displays, display_names)
            if model.scene is not None:
                self._viewport_inspector.set_scene(model.scene)
            self._viewport_inspector.set_viewport(
                model.target, model.extras.get("current_display")
            )

        elif kind is InspectorKind.PIPELINE:
            if file_path is not None:
                self._pipeline_inspector.load_pipeline_file(file_path)
            else:
                self._pipeline_inspector.set_pipeline(model.target, f"Pipeline: {model.label}")

        elif kind is InspectorKind.TEXTURE:
            if file_path is not None:
                self._texture_inspector.set_texture_by_path(file_path)
            elif model.target is None:
                self._texture_inspector.set_texture(None, "")
            else:
                self._texture_inspector.set_texture(model.target, model.label)

        elif kind is InspectorKind.MESH:
            if file_path is not None:
                self._mesh_inspector.set_mesh_by_path(file_path)
            elif model.target is None:
                self._mesh_inspector.set_mesh(None, "")
            else:
                self._mesh_inspector.set_mesh(model.target, model.label)

        elif kind is InspectorKind.GLB:
            if model.target is not None:
                self._glb_inspector.set_glb_asset(model.target, model.label)
            elif file_path is not None:
                self._glb_inspector.set_glb_by_path(file_path)

        elif kind is InspectorKind.RENDER_TARGET:
            self._render_target_inspector.set_render_target(model.target, model.scene)

        self._show_panel(panel)

    # ------------------------------------------------------------------
    # Panel → controller change relays
    # ------------------------------------------------------------------

    def _emit_material_changed(self) -> None:
        if self._on_material_changed is not None:
            self._on_material_changed()

    def _emit_display_changed(self) -> None:
        if self._on_display_changed is not None:
            self._on_display_changed()

    def _emit_viewport_changed(self) -> None:
        if self._on_viewport_changed is not None:
            self._on_viewport_changed()

    def _emit_pipeline_changed(self) -> None:
        if self._on_pipeline_changed is not None:
            self._on_pipeline_changed()
