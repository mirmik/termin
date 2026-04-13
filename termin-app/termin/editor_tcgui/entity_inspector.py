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
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.combo_box import ComboBox
from tcgui.widgets.grid_layout import GridLayout
from tcgui.widgets.units import px
from tcgui.widgets.input_dialog import show_input_dialog

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


class EntityPropertyEditCommand(UndoCommand):
    """Undo command for editing entity properties."""

    def __init__(self, entity: Entity, property_name: str, old_value: Any, new_value: Any):
        self._entity = entity
        self._property_name = property_name
        self._old_value = old_value
        self._new_value = new_value

    def _apply(self, value: Any) -> None:
        if self._property_name == "name":
            self._entity.name = str(value)
            return
        if self._property_name == "layer":
            self._entity.layer = int(value)

    def do(self) -> None:
        self._apply(self._new_value)

    def undo(self) -> None:
        self._apply(self._old_value)

    def merge_with(self, other: UndoCommand) -> bool:
        if not isinstance(other, EntityPropertyEditCommand):
            return False
        if other._entity is not self._entity:
            return False
        if other._property_name != self._property_name:
            return False
        self._new_value = other._new_value
        return True


class RecursiveLayerChangeCommand(UndoCommand):
    """Undo command for changing layer on entity descendants."""

    def __init__(self, entities_and_old_layers: list[tuple[Entity, int]], new_layer: int):
        self._entities_and_old_layers = entities_and_old_layers
        self._new_layer = new_layer

    def do(self) -> None:
        for entity, _ in self._entities_and_old_layers:
            entity.layer = self._new_layer

    def undo(self) -> None:
        for entity, old_layer in self._entities_and_old_layers:
            entity.layer = old_layer

    def merge_with(self, other: UndoCommand) -> bool:
        return False


class EntityInspector(VStack):
    """Full entity inspector: entity props + transform + components + field editor."""

    def __init__(self, resources=None) -> None:
        super().__init__()
        self.spacing = 4

        self._entity: Optional[Entity] = None
        self._resources = resources
        self._scene = None
        self._push_undo_command: Optional[Callable[[UndoCommand, bool], None]] = None
        self._updating_entity_props: bool = False

        self.on_transform_changed: Optional[Callable[[], None]] = None
        self.on_component_changed: Optional[Callable[[], None]] = None
        # on_component_field_changed(component, field_key, new_value)
        self.on_component_field_changed: Optional[Callable[[Any, str, Any], None]] = None

        inspector_title = Label()
        inspector_title.text = "Inspector"
        self.add_child(inspector_title)

        # Entity section
        entity_title = Label()
        entity_title.text = "Entity"
        self.add_child(entity_title)

        self._entity_grid = GridLayout(columns=3)
        self._entity_grid.column_spacing = 4
        self._entity_grid.row_spacing = 4
        self._entity_grid.set_column_stretch(1, 1.0)
        self.add_child(self._entity_grid)

        name_lbl = Label()
        name_lbl.text = "Name:"
        name_lbl.preferred_width = px(96)
        self._entity_grid.add(name_lbl, 0, 0)
        self._name_input = TextInput()
        self._name_input.on_submit = self._on_name_submitted
        self._entity_grid.add(self._name_input, 0, 1, 1, 2)

        uuid_lbl = Label()
        uuid_lbl.text = "UUID:"
        uuid_lbl.preferred_width = px(96)
        self._entity_grid.add(uuid_lbl, 1, 0)
        self._uuid_value = Label()
        self._uuid_value.color = (0.55, 0.60, 0.68, 1.0)
        self._entity_grid.add(self._uuid_value, 1, 1, 1, 2)

        layer_lbl = Label()
        layer_lbl.text = "Layer:"
        layer_lbl.preferred_width = px(96)
        self._entity_grid.add(layer_lbl, 2, 0)
        self._layer_combo = ComboBox()
        self._layer_combo.on_changed = self._on_layer_changed
        self._entity_grid.add(self._layer_combo, 2, 1)

        self._apply_layer_btn = Button()
        self._apply_layer_btn.text = "↓"
        self._apply_layer_btn.preferred_width = px(24)
        self._apply_layer_btn.tooltip = "Apply layer to all children"
        self._apply_layer_btn.on_click = self._on_apply_layer_to_children
        self._entity_grid.add(self._apply_layer_btn, 2, 2)

        self.add_child(Separator())

        # Transform inspector
        self._transform_inspector = TransformInspector()
        self._transform_inspector.on_transform_changed = self._on_transform_changed
        self.add_child(self._transform_inspector)

        # Components list header
        comp_header = HStack()
        comp_header.spacing = 4
        comp_lbl = Label()
        comp_lbl.text = "Components"
        comp_lbl.stretch = True
        comp_header.add_child(comp_lbl)

        self._add_comp_btn = Button()
        self._add_comp_btn.text = "+"
        self._add_comp_btn.preferred_width = px(24)
        self._add_comp_btn.on_click = self._show_add_component_menu
        comp_header.add_child(self._add_comp_btn)
        self.add_child(comp_header)

        self._comp_list = ListWidget()
        self._comp_list.item_height = 22
        self._comp_list.item_spacing = 1
        self._comp_list.preferred_height = px(130)
        self._comp_list.on_select = lambda idx, item: self._on_component_selected(idx)
        self._comp_list.on_context_menu = (
            lambda idx, item, x, y: self._on_component_context_menu(idx, x, y)
        )
        self.add_child(self._comp_list)

        # Component field editor
        self._field_panel = InspectFieldPanel(resources)
        self._field_panel.on_field_changed = self._on_field_changed
        self.add_child(self._field_panel)

        # Current component reference (for undo/context menu)
        self._selected_comp_ref = None

        self._update_layer_combo()
        self._set_enabled(False)

    def _set_enabled(self, enabled: bool) -> None:
        self._name_input.enabled = enabled
        self._name_input.focusable = enabled
        self._layer_combo.enabled = enabled
        self._apply_layer_btn.enabled = enabled
        self._add_comp_btn.enabled = enabled

    def set_undo_command_handler(self, handler: Optional[Callable[[UndoCommand, bool], None]]) -> None:
        self._push_undo_command = handler
        self._transform_inspector.set_undo_command_handler(handler)

    def set_scene(self, scene) -> None:
        self._scene = scene
        self._update_layer_combo()
        self._refresh_entity_props()

    def _update_layer_combo(self) -> None:
        old_cb = self._layer_combo.on_changed
        self._layer_combo.on_changed = None
        self._layer_combo.clear()
        for i in range(64):
            name = f"Layer {i}"
            if self._scene is not None:
                try:
                    scene_name = self._scene.get_layer_name(i)
                    if scene_name:
                        name = scene_name
                except Exception as e:
                    log.error(f"EntityInspector: get_layer_name({i}) failed: {e}")
            self._layer_combo.add_item(name)
        self._layer_combo.on_changed = old_cb
        if self._ui is not None:
            self._ui.request_layout()

    def set_target(self, obj: Optional[object]) -> None:
        if isinstance(obj, Entity):
            ent = obj
        elif isinstance(obj, (Transform3, GeneralTransform3)):
            ent = obj.entity
        else:
            ent = None

        self._entity = ent
        self._selected_comp_ref = None

        self._set_enabled(ent is not None)
        self._refresh_entity_props()
        self._transform_inspector.set_target(ent)
        self._rebuild_component_list()
        self._field_panel.set_target(None)
        if self._ui is not None:
            self._ui.request_layout()

    def _refresh_entity_props(self) -> None:
        self._updating_entity_props = True
        try:
            if self._entity is None:
                self._name_input.text = ""
                self._uuid_value.text = ""
                self._layer_combo.selected_index = -1
                return
            self._name_input.text = self._entity.name or ""
            self._uuid_value.text = self._entity.uuid or "-"
            layer_idx = int(self._entity.layer)
            if 0 <= layer_idx < self._layer_combo.item_count:
                self._layer_combo.selected_index = layer_idx
            else:
                self._layer_combo.selected_index = -1
        finally:
            self._updating_entity_props = False

    def _on_name_submitted(self, text: str) -> None:
        if self._updating_entity_props or self._entity is None:
            return

        new_name = text.strip() or "entity"
        old_name = self._entity.name
        if new_name == old_name:
            return

        if self._push_undo_command is not None:
            cmd = EntityPropertyEditCommand(self._entity, "name", old_name, new_name)
            self._push_undo_command(cmd, False)
        else:
            self._entity.name = new_name

        if self.on_component_changed is not None:
            self.on_component_changed()

    def _on_layer_changed(self, index: int, _text: str) -> None:
        if self._updating_entity_props or self._entity is None:
            return
        if index < 0:
            return

        old_layer = int(self._entity.layer)
        new_layer = int(index)
        if old_layer == new_layer:
            return

        if self._push_undo_command is not None:
            cmd = EntityPropertyEditCommand(self._entity, "layer", old_layer, new_layer)
            self._push_undo_command(cmd, False)
        else:
            self._entity.layer = new_layer

        if self.on_component_changed is not None:
            self.on_component_changed()

    def _collect_descendants(self, entity: Entity, out: list[tuple[Entity, int]]) -> None:
        if entity.transform is None:
            return
        for child_transform in entity.transform.children:
            child_entity = child_transform.entity
            if child_entity is None:
                continue
            out.append((child_entity, int(child_entity.layer)))
            self._collect_descendants(child_entity, out)

    def _on_apply_layer_to_children(self) -> None:
        if self._entity is None:
            return

        new_layer = int(self._entity.layer)
        entities_and_old_layers: list[tuple[Entity, int]] = []
        self._collect_descendants(self._entity, entities_and_old_layers)
        if not entities_and_old_layers:
            return

        has_changes = any(old_layer != new_layer for _, old_layer in entities_and_old_layers)
        if not has_changes:
            return

        if self._push_undo_command is not None:
            cmd = RecursiveLayerChangeCommand(entities_and_old_layers, new_layer)
            self._push_undo_command(cmd, False)
        else:
            for ent, _old in entities_and_old_layers:
                ent.layer = new_layer

        if self.on_component_changed is not None:
            self.on_component_changed()

    def refresh_transform(self) -> None:
        self._transform_inspector.refresh_transform()

    def _rebuild_component_list(self) -> None:
        if self._entity is None:
            self._comp_list.set_items([])
            return

        items = []
        for ref in self._entity.tc_components:
            items.append({"text": self._get_component_display_name(ref)})
        for soa_name in self._entity.soa_component_names:
            items.append({"text": f"[SoA] {soa_name}"})
        self._comp_list.set_items(items)
        self._comp_list.selected_index = -1
        if self._ui is not None:
            self._ui.request_layout()

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
        if self._ui is not None:
            self._ui.request_layout()

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
        self._show_add_component_menu_at(None, None)

    def _show_add_component_menu_at(self, x: float | None, y: float | None) -> None:
        if self._entity is None:
            return
        from termin.entity import ComponentRegistry

        component_names = ComponentRegistry.instance().list_all()
        items = [MenuItem(name, on_click=(lambda n=name: self._add_component(n))) for name in component_names]
        ctx = Menu()
        ctx.items = items

        ui = self._ui or self._add_comp_btn._ui
        if ui is None:
            return
        if x is None or y is None:
            x = self._add_comp_btn.x
            y = self._add_comp_btn.y + self._add_comp_btn.height
        ctx.show(ui, x, y)

    def _show_add_soa_component_menu_at(self, x: float | None, y: float | None) -> None:
        if self._entity is None:
            return
        from termin.entity._entity_native import soa_registry_get_all_info

        soa_infos = soa_registry_get_all_info()
        items = [
            MenuItem(
                info["name"],
                on_click=(lambda n=info["name"]: self._add_soa_component(n)),
            )
            for info in soa_infos
        ]
        if not items:
            items = [MenuItem("(No SoA types)", enabled=False)]

        ctx = Menu()
        ctx.items = items
        ui = self._ui or self._add_comp_btn._ui
        if ui is None:
            return
        if x is None or y is None:
            x = self._add_comp_btn.x
            y = self._add_comp_btn.y + self._add_comp_btn.height
        ctx.show(ui, x, y)

    def _on_component_context_menu(self, index: int, x: float, y: float) -> None:
        if self._entity is None or self._ui is None:
            return
        tc_components = self._entity.tc_components

        is_empty_area = index < 0
        is_soa = index >= len(tc_components) and not is_empty_area
        ref = tc_components[index] if not is_soa else None
        soa_name = ""
        if is_soa:
            soa_index = index - len(tc_components)
            if 0 <= soa_index < len(self._entity.soa_component_names):
                soa_name = self._entity.soa_component_names[soa_index]

        ctx = Menu()
        items: list[MenuItem] = []
        if not is_empty_area and not is_soa and ref is not None:
            items.append(MenuItem("Rename Component...", on_click=lambda r=ref: self._rename_component(r, index)))
            items.append(MenuItem("Remove Component", on_click=lambda r=ref: self._remove_component(r)))
        elif soa_name:
            items.append(MenuItem("Remove SoA Component", on_click=lambda n=soa_name: self._remove_soa_component(n)))

        if items:
            items.append(MenuItem.sep())
        items.append(MenuItem("Add Component...", on_click=lambda px=x, py=y: self._show_add_component_menu_at(px, py)))
        items.append(MenuItem("Add SoA Component...", on_click=lambda px=x, py=y: self._show_add_soa_component_menu_at(px, py)))
        ctx.items = items
        ctx.show(self._ui, x, y)

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

    def _add_soa_component(self, name: str) -> None:
        if self._entity is None:
            return
        try:
            self._entity.add_soa_by_name(name)
        except Exception as e:
            log.error(f"Failed to add SoA component {name}: {e}")
            return
        self._rebuild_component_list()
        if self.on_component_changed is not None:
            self.on_component_changed()

    def _rename_component(self, ref, index: int) -> None:
        if self._entity is None or self._ui is None:
            return
        current_name = ref.get_field("display_name") or ""
        show_input_dialog(
            self._ui,
            title="Rename Component",
            message="Name:",
            default=current_name,
            on_result=lambda value, r=ref, idx=index: self._apply_component_rename(r, idx, value),
        )

    def _apply_component_rename(self, ref, index: int, value: str | None) -> None:
        if self._entity is None or value is None:
            return
        try:
            ref.set_field("display_name", value.strip())
        except Exception as e:
            log.error(f"Failed to rename component: {e}")
            return
        self._rebuild_component_list()
        self._comp_list.selected_index = index
        self._on_component_selected(index)
        if self.on_component_changed is not None:
            self.on_component_changed()

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
        if self._ui is not None:
            self._ui.request_layout()

        if self.on_component_changed is not None:
            self.on_component_changed()

    def _remove_soa_component(self, soa_name: str) -> None:
        if self._entity is None:
            return
        try:
            self._entity.remove_soa_by_name(soa_name)
        except Exception as e:
            log.error(f"Failed to remove SoA component {soa_name}: {e}")
            return
        self._selected_comp_ref = None
        self._field_panel.set_target(None)
        self._rebuild_component_list()
        if self._ui is not None:
            self._ui.request_layout()
        if self.on_component_changed is not None:
            self.on_component_changed()
