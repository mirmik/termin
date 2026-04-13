"""InspectorController for tcgui — manages inspector panel switching."""

from __future__ import annotations

from typing import Callable, Optional, List, Any
from pathlib import Path

from tcgui.widgets.vstack import VStack
from tcgui.widgets.widget import Widget

from termin.editor_tcgui.entity_inspector import EntityInspector
from termin.editor_tcgui.material_inspector import MaterialInspectorTcgui
from termin.editor_tcgui.display_inspector import DisplayInspectorTcgui
from termin.editor_tcgui.viewport_inspector import ViewportInspectorTcgui
from termin.editor_tcgui.pipeline_inspector import PipelineInspectorTcgui
from termin.editor_tcgui.texture_inspector import TextureInspectorTcgui
from termin.editor_tcgui.mesh_inspector import MeshInspectorTcgui
from termin.editor_tcgui.glb_inspector import GLBInspectorTcgui


class InspectorControllerTcgui:
    """Manages inspector panels for the tcgui editor.

    Instead of QStackedWidget, uses widget.visible toggling.
    Panels are all children of the container VStack; only one is visible at a time.
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
        graphics=None,
    ) -> None:
        self._resource_manager = resource_manager
        self._push_undo_command = push_undo_command
        self._container = container
        self._graphics = graphics
        self._scene = None
        self._on_material_changed = on_material_changed
        self._on_display_changed = on_display_changed
        self._on_viewport_changed = on_viewport_changed
        self._on_pipeline_changed = on_pipeline_changed

        # Entity inspector (primary)
        self._entity_inspector = EntityInspector(resource_manager)
        self._entity_inspector.set_undo_command_handler(push_undo_command)
        self._entity_inspector.on_transform_changed = on_transform_changed
        self._entity_inspector.on_component_changed = on_component_changed
        container.add_child(self._entity_inspector)

        self._material_inspector = MaterialInspectorTcgui(resource_manager)
        self._display_inspector = DisplayInspectorTcgui()
        self._viewport_inspector = ViewportInspectorTcgui(resource_manager)
        self._pipeline_inspector = PipelineInspectorTcgui(resource_manager)
        self._texture_inspector = TextureInspectorTcgui(resource_manager)
        self._mesh_inspector = MeshInspectorTcgui(resource_manager)
        self._glb_inspector = GLBInspectorTcgui(resource_manager)

        self._material_inspector.on_changed = self._emit_material_changed
        self._display_inspector.on_changed = self._emit_display_changed
        self._viewport_inspector.on_changed = self._emit_viewport_changed
        self._pipeline_inspector.on_changed = self._emit_pipeline_changed

        for panel in (
            self._material_inspector,
            self._display_inspector,
            self._viewport_inspector,
            self._pipeline_inspector,
            self._texture_inspector,
            self._mesh_inspector,
            self._glb_inspector,
        ):
            panel.visible = False
            container.add_child(panel)

        self._panels: list[Widget] = [
            self._entity_inspector,
            self._material_inspector,
            self._display_inspector,
            self._viewport_inspector,
            self._pipeline_inspector,
            self._texture_inspector,
            self._mesh_inspector,
            self._glb_inspector,
        ]
        self._active_panel: Widget = self._entity_inspector

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def entity_inspector(self) -> EntityInspector:
        return self._entity_inspector

    # ------------------------------------------------------------------
    # Panel switching
    # ------------------------------------------------------------------

    def _show_panel(self, panel: Widget) -> None:
        for p in self._panels:
            p.visible = False
        panel.visible = True
        self._active_panel = panel
        if self._container._ui is not None:
            self._container._ui.request_layout()

    def set_scene(self, scene) -> None:
        self._scene = scene
        self._entity_inspector.set_scene(scene)
        self._viewport_inspector.set_scene(scene)

    def show_entity_inspector(self, entity=None) -> None:
        self._show_panel(self._entity_inspector)
        self._entity_inspector.set_target(entity)

    def show_material_inspector(self, material_name: str | None = None) -> None:
        if material_name is None:
            self._material_inspector.set_target(None, "No material selected.")
            self._show_panel(self._material_inspector)
            return
        material = self._resource_manager.get_material(material_name)
        self._material_inspector.set_target(material, f"Material: {material_name}")
        self._show_panel(self._material_inspector)

    def show_material_inspector_for_file(self, file_path: str) -> None:
        name = Path(file_path).stem
        self.show_material_inspector(name)
        self._material_inspector.set_target(
            self._resource_manager.get_material(name),
            f"File: {file_path}",
        )

    def show_display_inspector(self, display=None, name: str = "") -> None:
        self._display_inspector.set_display(display, name)
        self._show_panel(self._display_inspector)

    def show_viewport_inspector(
        self,
        viewport=None,
        displays: Optional[List] = None,
        display_names: Optional[dict] = None,
        scene=None,
        current_display=None,
    ) -> None:
        if displays is not None:
            self._viewport_inspector.set_displays(displays, display_names)
        if scene is not None:
            self._viewport_inspector.set_scene(scene)
        self._viewport_inspector.set_viewport(viewport, current_display)
        self._show_panel(self._viewport_inspector)

    def show_pipeline_inspector_for_file(self, file_path: str) -> None:
        name = Path(file_path).stem
        asset = self._resource_manager.get_pipeline_asset(name)
        pipeline = asset.data if asset is not None else None
        self._pipeline_inspector.set_pipeline(pipeline, f"File: {file_path}")
        self._show_panel(self._pipeline_inspector)

    def show_texture_inspector(self, texture_name: str | None = None) -> None:
        if texture_name is None:
            self._texture_inspector.set_texture(None, "")
            self._show_panel(self._texture_inspector)
            return
        texture = self._resource_manager.get_texture(texture_name)
        self._texture_inspector.set_texture(texture, texture_name)
        self._show_panel(self._texture_inspector)

    def show_texture_inspector_for_file(self, file_path: str) -> None:
        self._texture_inspector.set_texture_by_path(file_path)
        self._show_panel(self._texture_inspector)

    def show_mesh_inspector(self, mesh_name: str | None = None) -> None:
        if mesh_name is None:
            self._mesh_inspector.set_mesh(None, "")
            self._show_panel(self._mesh_inspector)
            return
        mesh_asset = self._resource_manager.get_mesh_asset(mesh_name)
        self._mesh_inspector.set_mesh(mesh_asset, mesh_name)
        self._show_panel(self._mesh_inspector)

    def show_mesh_inspector_for_file(self, file_path: str) -> None:
        self._mesh_inspector.set_mesh_by_path(file_path)
        self._show_panel(self._mesh_inspector)

    def show_glb_inspector_for_file(self, file_path: str) -> None:
        name = Path(file_path).stem
        glb_asset = self._resource_manager.get_glb_asset(name)
        if glb_asset is not None:
            self._glb_inspector.set_glb_asset(glb_asset, name)
        else:
            self._glb_inspector.set_glb_by_path(file_path)
        self._show_panel(self._glb_inspector)

    def set_entity_target(self, target: Any) -> None:
        self._entity_inspector.set_target(target)

    def clear(self) -> None:
        self._entity_inspector.set_target(None)
        self._show_panel(self._entity_inspector)

    def resync_from_tree_selection(self, node_data) -> None:
        """Sync inspector from tree selection (pass node.data)."""
        from termin.visualization.core.entity import Entity
        if isinstance(node_data, Entity):
            self.show_entity_inspector(node_data)
        else:
            self._entity_inspector.set_target(node_data)
            self._show_panel(self._entity_inspector)

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
