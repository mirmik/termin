"""Native production Entity Inspector projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import weakref

from termin.editor_core.entity_inspector_model import (
    EntityInspectorController,
    EntityInspectorSnapshot,
)

InputDialogHandler = Callable[[str, str, str, Callable[[str | None], None]], None]
from termin.editor_core.inspector_resources import InspectorResourceCatalog
from termin.editor_native.inspector_fields import (
    ColorDialogHandler,
    LayerMaskDialogHandler,
    NativeInspectorFields,
    TexturePreviewHandler,
    build_native_inspector_fields,
)
from termin.gui_native import (
    CollectionItem,
    CollectionModel,
    Color,
    CommandKind,
    CommandData,
    CommandModel,
    Document,
    EdgeInsets,
    Point,
    Rect,
    Size,
    WidgetRef,
)


@dataclass
class NativeEntityInspector:
    document: Document
    controller: EntityInspectorController
    root: WidgetRef
    name_input: object
    uuid_value: object
    layer_combo: object
    apply_layer_button: object
    transform_boxes: tuple[tuple[object, object, object], ...]
    component_model: CollectionModel
    component_list: object
    add_component_model: CommandModel
    add_component_menu: object
    add_soa_component_model: CommandModel
    add_soa_component_menu: object
    component_context_model: CommandModel
    component_context_menu: object
    scroll: object
    content: WidgetRef
    extension_host: WidgetRef
    fields: NativeInspectorFields
    viewport: Callable[[], Rect]
    request_render: Callable[[], None]
    show_input: InputDialogHandler | None
    add_component_types: dict[str, str]
    add_soa_component_types: dict[str, str]
    context_menu_position: Point | None = None
    updating: bool = False

    def apply_snapshot(self, snapshot: EntityInspectorSnapshot) -> None:
        self.updating = True
        try:
            self.name_input.text = snapshot.name
            self.name_input.widget.enabled = snapshot.entity is not None
            self.uuid_value.text = snapshot.uuid or "No entity selected"
            if self.layer_combo.item_count != len(snapshot.layer_names):
                self.layer_combo.clear()
                for name in snapshot.layer_names:
                    self.layer_combo.add_item(name)
            self.layer_combo.selected_index = snapshot.layer
            self.layer_combo.widget.enabled = snapshot.entity is not None
            self.apply_layer_button.widget.enabled = snapshot.entity is not None
            transform_values = (
                snapshot.transform.position,
                snapshot.transform.rotation_degrees,
                snapshot.transform.scale,
            )
            for boxes, values in zip(self.transform_boxes, transform_values, strict=True):
                for box, value in zip(boxes, values, strict=True):
                    box.value = value
                    box.widget.enabled = snapshot.transform.enabled
            self.component_model.set_items(
                [
                    CollectionItem(
                        component.stable_id,
                        component.label,
                        "" if component.label == component.type_name else component.type_name,
                    )
                    for component in snapshot.components
                ]
            )
            if snapshot.selected_component >= 0:
                self.component_list.select(snapshot.selected_component)
            else:
                self.component_list.clear_selection()
            self.fields.rebuild(snapshot.fields)
        finally:
            self.updating = False
        self.request_render()

    def set_target(self, target) -> None:
        self.controller.set_target(target)

    def set_scene(self, scene) -> None:
        self.controller.set_scene(scene)

    def show_add_component_menu(self, position: Point | None = None) -> None:
        categories: dict[str, CommandModel] = {}
        commands = []
        self.add_component_types.clear()
        for component_type in self.controller.available_component_types():
            submenu = categories.get(component_type.category)
            if submenu is None:
                submenu = CommandModel()
                categories[component_type.category] = submenu
                commands.append(
                    CommandData(
                        f"category:{component_type.category}",
                        component_type.category,
                        submenu=submenu,
                    )
                )
            stable_id = f"component:{len(self.add_component_types)}"
            self.add_component_types[stable_id] = component_type.type_name
            submenu.append(CommandData(stable_id, component_type.display_name))
        if not commands:
            commands.append(CommandData("empty", "(No component types)", enabled=False))
        self.add_component_model.set_commands(commands)
        if position is None:
            bounds = self.component_list.widget.bounds
            position = Point(bounds.x, bounds.y + bounds.height)
        if not self.add_component_menu.show(
            position,
            self.viewport(),
        ):
            raise RuntimeError("failed to show native add component menu")
        self.request_render()

    def show_add_soa_component_menu(self, position: Point | None = None) -> None:
        commands = []
        self.add_soa_component_types.clear()
        for type_name in self.controller.available_soa_component_types():
            stable_id = f"soa:{len(self.add_soa_component_types)}"
            self.add_soa_component_types[stable_id] = type_name
            commands.append(CommandData(stable_id, type_name))
        if not commands:
            commands.append(CommandData("empty", "(No SoA component types)", enabled=False))
        self.add_soa_component_model.set_commands(commands)
        if position is None:
            bounds = self.component_list.widget.bounds
            position = Point(bounds.x, bounds.y + bounds.height)
        if not self.add_soa_component_menu.show(position, self.viewport()):
            raise RuntimeError("failed to show native add SoA component menu")
        self.request_render()

    def show_component_context_menu(self, index: int, x: float, y: float) -> None:
        snapshot = self.controller.snapshot
        if index >= len(snapshot.components):
            index = -1
        self.context_menu_position = Point(x, y)
        if index >= 0:
            self.controller.select_component(index)
        commands = []
        if index >= 0:
            component = snapshot.components[index]
            if not component.soa and self.show_input is not None:
                commands.append(CommandData("rename-component", "Rename Component..."))
            commands.append(
                CommandData(
                    "remove-component",
                    "Remove SoA Component" if component.soa else "Remove Component",
                )
            )
            commands.append(CommandData("separator", kind=CommandKind.Separator))
        commands.append(CommandData("add-component", "Add Component..."))
        commands.append(CommandData("add-soa-component", "Add SoA Component..."))
        self.component_context_model.set_commands(commands)
        if not self.component_context_menu.show(Point(x, y), self.viewport()):
            raise RuntimeError("failed to show native component context menu")
        self.request_render()

    def rename_selected_component(self) -> None:
        if self.show_input is None:
            raise RuntimeError("native component rename requested without an input dialog service")
        self.show_input(
            "Rename Component",
            "Name:",
            self.controller.selected_component_display_name(),
            self._apply_component_rename,
        )

    def _apply_component_rename(self, value: str | None) -> None:
        if value is not None:
            self.controller.rename_selected_component(value)

    def set_extension_panel(self, panel: WidgetRef | None) -> None:
        self.clear_extension_panel()
        if panel is None:
            return
        separator = self.document.create_hstack("native-component-extension-separator")
        separator.set_layout_background(Color(0.24, 0.26, 0.31, 1.0))
        self.extension_host.add_fixed_child(separator, 1.0)
        self.extension_host.add_preferred_child(panel)
        self.extension_host.visible = True
        self.request_render()

    def clear_extension_panel(self) -> None:
        for child in tuple(self.extension_host.children):
            if not self.document.destroy_widget_recursive(child.handle):
                raise RuntimeError("failed to destroy native component extension panel")
        self.extension_host.visible = False
        self.request_render()


def build_native_entity_inspector(
    document: Document,
    controller: EntityInspectorController,
    *,
    request_render: Callable[[], None],
    viewport: Callable[[], Rect],
    show_color_dialog: ColorDialogHandler | None = None,
    show_layer_mask_dialog: LayerMaskDialogHandler | None = None,
    show_texture_preview: TexturePreviewHandler | None = None,
    resource_catalog: InspectorResourceCatalog | None = None,
    show_input: InputDialogHandler | None = None,
) -> NativeEntityInspector:
    root = document.create_vstack("native-entity-inspector")
    root.stable_id = "editor.inspector.entity"
    root.preferred_size = Size(360.0, 626.0)
    content = document.create_vstack("native-entity-inspector-scroll-content")
    content.set_layout_padding(EdgeInsets(6.0, 6.0, 6.0, 6.0))
    content.set_layout_spacing(4.0)
    scroll = document.create_scroll_area("native-entity-inspector-scroll")
    scroll.set_content(content)
    root.add_stretch_child(scroll.widget)

    title = document.create_label("Inspector", "native-entity-inspector-title")
    content.add_fixed_child(title, 28.0)

    name_row = document.create_hstack("native-inspector-entity-name-row")
    name_row.set_layout_spacing(4.0)
    name_label = document.create_label("Name", "native-inspector-entity-name-label")
    name_row.add_fixed_child(name_label, 72.0)
    name_input = document.create_text_input()
    name_row.add_stretch_child(name_input.widget)
    content.add_fixed_child(name_row, 30.0)

    uuid_row = document.create_hstack("native-inspector-entity-uuid-row")
    uuid_row.set_layout_spacing(4.0)
    uuid_label = document.create_label("UUID", "native-inspector-entity-uuid-label")
    uuid_row.add_fixed_child(uuid_label, 72.0)
    uuid_value = document.create_status_bar("No entity selected")
    uuid_row.add_stretch_child(uuid_value.widget)
    content.add_fixed_child(uuid_row, 26.0)

    layer_row = document.create_hstack("native-inspector-entity-layer-row")
    layer_row.set_layout_spacing(4.0)
    layer_label = document.create_label("Layer", "native-inspector-entity-layer-label")
    layer_row.add_fixed_child(layer_label, 72.0)
    layer_combo = document.create_combo_box()
    layer_row.add_stretch_child(layer_combo.widget)
    apply_layer_button = document.create_button("↓", "native-inspector-apply-layer")
    layer_row.add_fixed_child(apply_layer_button.widget, 32.0)
    content.add_fixed_child(layer_row, 30.0)

    transform_boxes = []
    for key, label_text in (
        ("position", "Position"),
        ("rotation", "Rotation (deg)"),
        ("scale", "Scale"),
    ):
        row = document.create_hstack(f"native-inspector-transform-{key}")
        row.set_layout_spacing(3.0)
        label = document.create_label(label_text, f"native-inspector-transform-{key}-label")
        row.add_fixed_child(label, 104.0)
        boxes = []
        for axis in "xyz":
            box = document.create_spin_box(1.0 if key == "scale" else 0.0)
            box.set_range(-1.0e6, 1.0e6)
            box.step = 0.1
            box.decimals = 3
            box.widget.stable_id = f"editor.inspector.transform.{key}.{axis}"
            row.add_stretch_child(box.widget)
            boxes.append(box)
        transform_boxes.append(tuple(boxes))
        content.add_fixed_child(row, 30.0)

    component_label = document.create_label("Components", "native-inspector-components-label")
    content.add_fixed_child(component_label, 26.0)
    component_model = CollectionModel()
    component_list = document.create_list_widget(component_model)
    component_list.set_row_height(24.0)
    component_list.set_row_spacing(1.0)
    content.add_fixed_child(component_list.widget, 150.0)

    add_component_model = CommandModel()
    add_component_menu = document.create_menu(add_component_model)
    add_soa_component_model = CommandModel()
    add_soa_component_menu = document.create_menu(add_soa_component_model)
    component_context_model = CommandModel()
    component_context_menu = document.create_menu(component_context_model)

    fields = build_native_inspector_fields(
        document,
        controller.fields,
        request_render=request_render,
        show_color_dialog=show_color_dialog,
        show_layer_mask_dialog=show_layer_mask_dialog,
        show_texture_preview=show_texture_preview,
        layer_names=lambda: controller.snapshot.layer_names,
        resource_catalog=resource_catalog,
    )
    content.add_preferred_child(fields.root)
    extension_host = document.create_vstack("native-component-extension-host")
    extension_host.set_layout_spacing(4.0)
    extension_host.visible = False
    content.add_preferred_child(extension_host)

    inspector = NativeEntityInspector(
        document=document,
        controller=controller,
        root=root,
        name_input=name_input,
        uuid_value=uuid_value,
        layer_combo=layer_combo,
        apply_layer_button=apply_layer_button,
        transform_boxes=tuple(transform_boxes),
        component_model=component_model,
        component_list=component_list,
        add_component_model=add_component_model,
        add_component_menu=add_component_menu,
        add_soa_component_model=add_soa_component_model,
        add_soa_component_menu=add_soa_component_menu,
        component_context_model=component_context_model,
        component_context_menu=component_context_menu,
        scroll=scroll,
        content=content,
        extension_host=extension_host,
        fields=fields,
        viewport=viewport,
        request_render=request_render,
        show_input=show_input,
        add_component_types={},
        add_soa_component_types={},
    )
    weak_inspector = weakref.ref(inspector)

    def current() -> NativeEntityInspector | None:
        return weak_inspector()

    def on_snapshot(snapshot: EntityInspectorSnapshot) -> None:
        owner = current()
        if owner is not None:
            owner.apply_snapshot(snapshot)

    def on_name_submitted(value: str) -> None:
        owner = current()
        if owner is not None and not owner.updating:
            owner.controller.set_name(value)

    def on_layer_changed(index: int, _text: str) -> None:
        owner = current()
        if owner is not None and not owner.updating and index >= 0:
            owner.controller.set_layer(index)

    def on_apply_layer() -> None:
        owner = current()
        if owner is not None and not owner.updating:
            owner.controller.apply_layer_to_descendants()

    def on_transform_changed(_value: float) -> None:
        owner = current()
        if owner is None or owner.updating:
            return
        values = tuple(
            tuple(box.value for box in boxes)
            for boxes in owner.transform_boxes
        )
        owner.controller.set_transform(values[0], values[1], values[2])
        owner.request_render()

    def on_component_selection(selected: list[int]) -> None:
        owner = current()
        if owner is not None and not owner.updating:
            owner.controller.select_component(selected[-1] if selected else -1)

    def on_add_component_activated(_index: int, _command_id: int, command) -> None:
        owner = current()
        if owner is None:
            return
        type_name = owner.add_component_types.get(command.stable_id)
        if type_name is not None:
            owner.controller.add_component(type_name)

    def on_add_soa_component_activated(_index: int, _command_id: int, command) -> None:
        owner = current()
        if owner is None:
            return
        type_name = owner.add_soa_component_types.get(command.stable_id)
        if type_name is not None:
            owner.controller.add_soa_component(type_name)

    def on_component_context(index: int, x: float, y: float) -> None:
        owner = current()
        if owner is not None and not owner.updating:
            owner.show_component_context_menu(index, x, y)

    def on_component_context_activated(_index: int, _command_id: int, command) -> None:
        owner = current()
        if owner is None:
            return
        if command.stable_id == "remove-component":
            owner.controller.remove_selected_component()
        elif command.stable_id == "rename-component":
            owner.rename_selected_component()
        elif command.stable_id == "add-component":
            owner.show_add_component_menu(owner.context_menu_position)
        elif command.stable_id == "add-soa-component":
            owner.show_add_soa_component_menu(owner.context_menu_position)

    name_input.connect_submitted(on_name_submitted)
    layer_combo.connect_changed(on_layer_changed)
    apply_layer_button.connect_clicked(on_apply_layer)
    for boxes in inspector.transform_boxes:
        for box in boxes:
            box.connect_changed(on_transform_changed)
    component_list.connect_selection_changed(on_component_selection)
    component_list.connect_context_menu_requested(on_component_context)
    add_component_menu.connect_activated(on_add_component_activated)
    add_soa_component_menu.connect_activated(on_add_soa_component_activated)
    component_context_menu.connect_activated(on_component_context_activated)
    controller.set_snapshot_changed_handler(on_snapshot)
    inspector.apply_snapshot(controller.snapshot)
    return inspector


__all__ = ["NativeEntityInspector", "build_native_entity_inspector"]
