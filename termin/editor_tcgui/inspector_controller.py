"""InspectorController for tcgui — manages inspector panel switching."""

from __future__ import annotations

from typing import Callable, Optional, List, Any

from tcgui.widgets.vstack import VStack
from tcgui.widgets.widget import Widget

from termin.editor_tcgui.entity_inspector import EntityInspector


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

        # Additional inspectors are stubbed as labels for now;
        # they will be implemented in follow-up phases.
        # Each has .visible controlled by show_* methods.
        self._panels: list[Widget] = [self._entity_inspector]
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
        # Stub: show entity inspector for now
        self._show_panel(self._entity_inspector)

    def show_material_inspector_for_file(self, file_path: str) -> None:
        self._show_panel(self._entity_inspector)

    def show_display_inspector(self, display=None, name: str = "") -> None:
        self._show_panel(self._entity_inspector)

    def show_viewport_inspector(
        self,
        viewport=None,
        displays: Optional[List] = None,
        display_names: Optional[dict] = None,
        scene=None,
        current_display=None,
    ) -> None:
        self._show_panel(self._entity_inspector)

    def show_pipeline_inspector_for_file(self, file_path: str) -> None:
        self._show_panel(self._entity_inspector)

    def show_texture_inspector(self, texture_name: str | None = None) -> None:
        self._show_panel(self._entity_inspector)

    def show_texture_inspector_for_file(self, file_path: str) -> None:
        self._show_panel(self._entity_inspector)

    def show_mesh_inspector(self, mesh_name: str | None = None) -> None:
        self._show_panel(self._entity_inspector)

    def show_mesh_inspector_for_file(self, file_path: str) -> None:
        self._show_panel(self._entity_inspector)

    def show_glb_inspector_for_file(self, file_path: str) -> None:
        self._show_panel(self._entity_inspector)

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
