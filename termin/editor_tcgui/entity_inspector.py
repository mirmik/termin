"""tcgui EntityInspector — entity properties, transform, components."""

from __future__ import annotations

from typing import Any, Callable, Optional

from tcbase import log
from tcgui.widgets.vstack import VStack
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.button import Button
from tcgui.widgets.list_widget import ListWidget
from tcgui.widgets.separator import Separator
from tcgui.widgets.menu import Menu, MenuItem
from tcgui.widgets.scroll_area import ScrollArea

from termin.visualization.core.entity import Entity
from termin.kinematic.transform import Transform3
from termin.kinematic.general_transform import GeneralTransform3
from termin.editor.undo_stack import UndoCommand
from termin.editor.editor_commands import (
    AddComponentCommand,
    RemoveComponentCommand,
    ComponentFieldEditCommand,
)
from termin.editor_tcgui.transform_inspector import TransformInspector
from termin.editor_tcgui.inspect_field_panel import InspectFieldPanel


class EntityInspector(VStack):
    """Full entity inspector: transform + components list + component field editor."""

    def __init__(self, resources=None) -> None:
        super().__init__()
        self.spacing = 6

        self._entity: Optional[Entity] = None
        self._resources = resources
        self._scene = None
        self._push_undo_command: Optional[Callable[[UndoCommand, bool], None]] = None

        self.on_transform_changed: Optional[Callable[[], None]] = None
        self.on_component_changed: Optional[Callable[[], None]] = None
        # on_component_field_changed(component, field_key, new_value)
        self.on_component_field_changed: Optional[Callable[[Any, str, Any], None]] = None

        # Entity name label
        self._name_label = Label()
        self._name_label.text = ""
        self.add_child(self._name_label)

        # Transform inspector
        self._transform_inspector = TransformInspector()
        self._transform_inspector.on_transform_changed = self._on_transform_changed
        self.add_child(self._transform_inspector)

        self.add_child(Separator())

        # Components list header
        comp_header = HStack()
        comp_header.spacing = 4
        comp_lbl = Label()
        comp_lbl.text = "Components"
        comp_header.add_child(comp_lbl)

        self._add_comp_btn = Button()
        self._add_comp_btn.text = "+"
        self._add_comp_btn.on_click = self._show_add_component_menu
        comp_header.add_child(self._add_comp_btn)
        self.add_child(comp_header)

        self._comp_list = ListWidget()
        self._comp_list.on_select = self._on_component_selected
        self.add_child(self._comp_list)

        # Component field editor
        self._field_panel = InspectFieldPanel(resources)
        self._field_panel.on_field_changed = self._on_field_changed
        self.add_child(self._field_panel)

        # Current component reference (for undo/context menu)
        self._selected_comp_ref = None

    def set_undo_command_handler(self, handler: Optional[Callable[[UndoCommand, bool], None]]) -> None:
        self._push_undo_command = handler
        self._transform_inspector.set_undo_command_handler(handler)

    def set_scene(self, scene) -> None:
        self._scene = scene

    def set_target(self, obj: Optional[object]) -> None:
        if isinstance(obj, Entity):
            ent = obj
        elif isinstance(obj, (Transform3, GeneralTransform3)):
            ent = obj.entity
        else:
            ent = None

        self._entity = ent
        self._selected_comp_ref = None

        if ent is not None:
            self._name_label.text = ent.name or "(unnamed)"
        else:
            self._name_label.text = ""

        self._transform_inspector.set_target(ent)
        self._rebuild_component_list()
        self._field_panel.set_target(None)

    def refresh_transform(self) -> None:
        self._transform_inspector.refresh_transform()

    def _rebuild_component_list(self) -> None:
        self._comp_list.items = []
        if self._entity is None:
            return

        items = []
        for ref in self._entity.tc_components:
            items.append(self._get_component_display_name(ref))
        for soa_name in self._entity.soa_component_names:
            items.append(f"[SoA] {soa_name}")
        self._comp_list.items = items
        self._comp_list.selected_index = -1

    def _get_component_display_name(self, ref) -> str:
        type_name = ref.type_name
        display_name = ref.get_field("display_name")
        if display_name:
            return f"{display_name} ({type_name})"
        return type_name

    def _on_component_selected(self, index: int) -> None:
        if self._entity is None or index < 0:
            self._selected_comp_ref = None
            self._field_panel.set_target(None)
            return

        tc_components = self._entity.tc_components
        if index >= len(tc_components):
            # SoA component — no field editing yet
            self._selected_comp_ref = None
            self._field_panel.set_target(None)
            return

        ref = tc_components[index]
        self._selected_comp_ref = ref
        self._field_panel.set_target(ref)

    def _on_transform_changed(self) -> None:
        if self.on_transform_changed is not None:
            self.on_transform_changed()

    def _on_field_changed(self, key: str, old_value: Any, new_value: Any) -> None:
        comp = self._selected_comp_ref
        if comp is None:
            return

        if self._push_undo_command is not None:
            field = self._field_panel._fields.get(key)
            if field is not None:
                field.set_value(comp, old_value)
                cmd = ComponentFieldEditCommand(
                    component=comp,
                    field=field,
                    old_value=old_value,
                    new_value=new_value,
                )
                self._push_undo_command(cmd, True)

        if self.on_component_field_changed is not None:
            self.on_component_field_changed(comp, key, new_value)
        if self.on_component_changed is not None:
            self.on_component_changed()

    def _show_add_component_menu(self) -> None:
        if self._entity is None:
            return
        from termin.entity import ComponentRegistry
        component_names = ComponentRegistry.instance().list_all()

        items = [
            MenuItem(name, on_click=(lambda n=name: self._add_component(n)))
            for name in component_names
        ]
        ctx = Menu()
        ctx.items = items

        # Show as context menu at the button position
        if self._add_comp_btn._ui is not None:
            x = self._add_comp_btn.x
            y = self._add_comp_btn.y + self._add_comp_btn.height
            w, h = ctx._compute_content_size()
            ctx.layout(x, y, w, h, self._add_comp_btn._ui._viewport_w, self._add_comp_btn._ui._viewport_h)
            self._add_comp_btn._ui.show_overlay(ctx, dismiss_on_outside=True)

    def _add_component(self, name: str) -> None:
        if self._entity is None:
            return
        try:
            ref = self._entity.add_component_by_name(name)
        except Exception as e:
            log.error(f"Failed to create component {name}: {e}")
            return

        if self._push_undo_command is not None:
            cmd = AddComponentCommand(self._entity, name, ref)
            self._push_undo_command(cmd, False)

        self._rebuild_component_list()

    def show_context_menu_for_component(self, index: int) -> None:
        """Show context menu for component at index."""
        if self._entity is None:
            return

        tc_components = self._entity.tc_components
        if index < 0 or index >= len(tc_components):
            return

        ref = tc_components[index]

        ctx = Menu()
        ctx.items = [
            MenuItem("Remove Component", on_click=lambda r=ref: self._remove_component(r)),
        ]
        # Show at mouse position via UI overlay (caller supplies coordinates)

    def _remove_component(self, ref) -> None:
        if self._entity is None:
            return
        type_name = ref.type_name
        if self._push_undo_command is not None:
            cmd = RemoveComponentCommand(self._entity, type_name)
            self._push_undo_command(cmd, False)
        else:
            self._entity.remove_component_ref(ref)

        self._selected_comp_ref = None
        self._field_panel.set_target(None)
        self._rebuild_component_list()

        if self.on_component_changed is not None:
            self.on_component_changed()
