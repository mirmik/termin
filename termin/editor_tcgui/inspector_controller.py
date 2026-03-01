"""InspectorController for tcgui — manages inspector panel switching."""

from __future__ import annotations

from typing import Callable, Optional, List, Any

from tcgui.widgets.vstack import VStack
from tcgui.widgets.widget import Widget
from tcgui.widgets.label import Label

from termin.editor_tcgui.entity_inspector import EntityInspector


class _InfoInspector(VStack):
    """Simple inspector placeholder for not-yet-ported panels."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self.spacing = 4
        hdr = Label()
        hdr.text = title
        self.add_child(hdr)
        self._text = Label()
        self._text.color = (0.62, 0.66, 0.74, 1.0)
        self.add_child(self._text)

    def set_message(self, msg: str) -> None:
        self._text.text = msg


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

        # Entity inspector (primary)
        self._entity_inspector = EntityInspector(resource_manager)
        self._entity_inspector.set_undo_command_handler(push_undo_command)
        self._entity_inspector.on_transform_changed = on_transform_changed
        self._entity_inspector.on_component_changed = on_component_changed
        container.add_child(self._entity_inspector)

        self._material_stub = _InfoInspector("Material Inspector")
        self._display_stub = _InfoInspector("Display Inspector")
        self._viewport_stub = _InfoInspector("Viewport Inspector")
        self._pipeline_stub = _InfoInspector("Pipeline Inspector")
        self._texture_stub = _InfoInspector("Texture Inspector")
        self._mesh_stub = _InfoInspector("Mesh Inspector")
        self._glb_stub = _InfoInspector("GLB Inspector")

        for panel in (
            self._material_stub,
            self._display_stub,
            self._viewport_stub,
            self._pipeline_stub,
            self._texture_stub,
            self._mesh_stub,
            self._glb_stub,
        ):
            panel.visible = False
            container.add_child(panel)

        self._panels: list[Widget] = [
            self._entity_inspector,
            self._material_stub,
            self._display_stub,
            self._viewport_stub,
            self._pipeline_stub,
            self._texture_stub,
            self._mesh_stub,
            self._glb_stub,
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
        self._entity_inspector.set_scene(scene)

    def show_entity_inspector(self, entity=None) -> None:
        self._show_panel(self._entity_inspector)
        self._entity_inspector.set_target(entity)

    def show_material_inspector(self, material_name: str | None = None) -> None:
        self._material_stub.set_message(
            f"Selected material: {material_name}" if material_name else "No material selected."
        )
        self._show_panel(self._material_stub)

    def show_material_inspector_for_file(self, file_path: str) -> None:
        self._material_stub.set_message(f"Selected file: {file_path}")
        self._show_panel(self._material_stub)

    def show_display_inspector(self, display=None, name: str = "") -> None:
        self._display_stub.set_message(f"Display: {name}" if name else "No display selected.")
        self._show_panel(self._display_stub)

    def show_viewport_inspector(
        self,
        viewport=None,
        displays: Optional[List] = None,
        display_names: Optional[dict] = None,
        scene=None,
        current_display=None,
    ) -> None:
        if viewport is None:
            self._viewport_stub.set_message("No viewport selected.")
        else:
            self._viewport_stub.set_message("Viewport selected.")
        self._show_panel(self._viewport_stub)

    def show_pipeline_inspector_for_file(self, file_path: str) -> None:
        self._pipeline_stub.set_message(f"Selected file: {file_path}")
        self._show_panel(self._pipeline_stub)

    def show_texture_inspector(self, texture_name: str | None = None) -> None:
        self._texture_stub.set_message(
            f"Selected texture: {texture_name}" if texture_name else "No texture selected."
        )
        self._show_panel(self._texture_stub)

    def show_texture_inspector_for_file(self, file_path: str) -> None:
        self._texture_stub.set_message(f"Selected file: {file_path}")
        self._show_panel(self._texture_stub)

    def show_mesh_inspector(self, mesh_name: str | None = None) -> None:
        self._mesh_stub.set_message(
            f"Selected mesh: {mesh_name}" if mesh_name else "No mesh selected."
        )
        self._show_panel(self._mesh_stub)

    def show_mesh_inspector_for_file(self, file_path: str) -> None:
        self._mesh_stub.set_message(f"Selected file: {file_path}")
        self._show_panel(self._mesh_stub)

    def show_glb_inspector_for_file(self, file_path: str) -> None:
        self._glb_stub.set_message(f"Selected file: {file_path}")
        self._show_panel(self._glb_stub)

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
