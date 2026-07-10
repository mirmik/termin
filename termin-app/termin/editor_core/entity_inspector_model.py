"""Toolkit-neutral entity inspector state and editing controller."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Callable

from termin.editor_core.editor_commands import (
    AddComponentCommand,
    AddSoAComponentCommand,
    ComponentFieldEditCommand,
    EntityPropertyEditCommand,
    RemoveComponentCommand,
    RemoveSoAComponentCommand,
    RecursiveLayerChangeCommand,
)
from termin.editor_core.inspector_fields_model import (
    InspectorFieldsController,
    InspectorFieldsSnapshot,
    collect_inspect_fields,
    collect_inspector_metadata,
)
from termin.editor_core.undo_stack import UndoCommand
from termin.inspect import InspectField
from termin.kinematic.general_transform import GeneralTransform3
from termin.kinematic.transform import Transform3
from termin.scene import Entity, TcComponentRef


_logger = logging.getLogger(__name__)
UndoHandler = Callable[[UndoCommand, bool], None]
ComponentSelectionHandler = Callable[[Entity | None, object | None], None]
_COMPONENT_CATEGORY_ORDER = (
    "Rendering",
    "Input",
    "UI",
    "Navigation",
    "Animation",
    "Physics",
    "Collision",
    "Audio",
    "Gameplay",
    "Project",
    "Editor/Internal",
    "Other",
)


@dataclass(frozen=True)
class EntityInspectorComponent:
    stable_id: str
    label: str
    type_name: str
    soa: bool = False


@dataclass(frozen=True)
class EntityInspectorComponentType:
    type_name: str
    display_name: str
    category: str


ComponentTypeCollector = Callable[[], tuple[EntityInspectorComponentType, ...]]


def _component_category_index(category: str) -> int:
    try:
        return _COMPONENT_CATEGORY_ORDER.index(category)
    except ValueError:
        return len(_COMPONENT_CATEGORY_ORDER)


def collect_component_types() -> tuple[EntityInspectorComponentType, ...]:
    from termin.scene import ComponentRegistry

    result = []
    for info in ComponentRegistry.instance().list_info():
        if bool(info.get("is_abstract", False)):
            continue
        type_name = str(info.get("name") or "")
        if not type_name:
            continue
        display_name = str(info.get("display_name") or type_name)
        category = str(info.get("category") or "Other").strip() or "Other"
        result.append(EntityInspectorComponentType(type_name, display_name, category))
    return tuple(
        sorted(
            result,
            key=lambda item: (
                _component_category_index(item.category),
                item.category.casefold(),
                item.display_name.casefold(),
                item.type_name.casefold(),
            ),
        )
    )


@dataclass(frozen=True)
class EntityInspectorSnapshot:
    entity: Entity | None
    name: str
    uuid: str
    layer: int
    layer_names: tuple[str, ...]
    components: tuple[EntityInspectorComponent, ...]
    selected_component: int
    fields: InspectorFieldsSnapshot


class EntityInspectorController:
    def __init__(
        self,
        *,
        undo_handler: UndoHandler | None = None,
        snapshot_changed: Callable[[EntityInspectorSnapshot], None] | None = None,
        field_collector=collect_inspect_fields,
        metadata_collector=collect_inspector_metadata,
        component_selection_changed: ComponentSelectionHandler | None = None,
        component_type_collector: ComponentTypeCollector = collect_component_types,
    ) -> None:
        self._scene = None
        self._entity: Entity | None = None
        self._selected_component = -1
        self._undo_handler = undo_handler
        self._snapshot_changed = snapshot_changed
        self._component_selection_changed = component_selection_changed
        self._component_type_collector = component_type_collector
        self.fields = InspectorFieldsController(
            field_collector=field_collector,
            metadata_collector=metadata_collector,
            change_handler=self._apply_component_field_change,
        )
        self._snapshot = self._build_snapshot()

    @property
    def snapshot(self) -> EntityInspectorSnapshot:
        return self._snapshot

    def set_snapshot_changed_handler(
        self,
        handler: Callable[[EntityInspectorSnapshot], None] | None,
    ) -> None:
        self._snapshot_changed = handler

    def set_component_selection_changed_handler(
        self,
        handler: ComponentSelectionHandler | None,
    ) -> None:
        self._component_selection_changed = handler

    def set_scene(self, scene) -> EntityInspectorSnapshot:
        self._scene = scene
        return self.refresh()

    def set_target(self, target) -> EntityInspectorSnapshot:
        if isinstance(target, Entity):
            entity = target
        elif isinstance(target, (Transform3, GeneralTransform3)):
            entity = target.entity
        else:
            entity = None
        self._entity = entity
        self._selected_component = -1
        self.fields.set_targets(())
        self._notify_component_selection(None)
        return self.refresh()

    def refresh(self) -> EntityInspectorSnapshot:
        self._reconcile_component_selection()
        self._snapshot = self._build_snapshot()
        if self._snapshot_changed is not None:
            self._snapshot_changed(self._snapshot)
        return self._snapshot

    def set_name(self, value: str) -> EntityInspectorSnapshot:
        if self._entity is None:
            return self._snapshot
        new_name = value.strip() or "entity"
        old_name = self._entity.name
        if new_name != old_name:
            self._execute(EntityPropertyEditCommand(self._entity, "name", old_name, new_name))
        return self.refresh()

    def set_layer(self, layer: int) -> EntityInspectorSnapshot:
        if self._entity is None:
            return self._snapshot
        if layer < 0 or layer >= 64:
            raise ValueError("entity layer must be in [0, 63]")
        old_layer = int(self._entity.layer)
        if layer != old_layer:
            self._execute(EntityPropertyEditCommand(self._entity, "layer", old_layer, layer))
        return self.refresh()

    def apply_layer_to_descendants(self) -> EntityInspectorSnapshot:
        if self._entity is None or self._entity.transform is None:
            return self._snapshot
        descendants: list[tuple[Entity, int]] = []
        self._collect_descendants(self._entity, descendants)
        new_layer = int(self._entity.layer)
        if any(old_layer != new_layer for _entity, old_layer in descendants):
            self._execute(RecursiveLayerChangeCommand(descendants, new_layer))
        return self.refresh()

    def select_component(self, index: int) -> EntityInspectorSnapshot:
        if self._entity is None or index < 0:
            self._selected_component = -1
            self.fields.set_targets(())
            self._notify_component_selection(None)
            return self.refresh()
        components = self._entity.tc_components
        if index >= len(components):
            self._selected_component = index
            self.fields.set_targets(())
            self._notify_component_selection(None)
            return self.refresh()
        self._selected_component = index
        self.fields.set_targets((components[index],))
        self._notify_component_selection(components[index])
        return self.refresh()

    def available_component_types(self) -> tuple[EntityInspectorComponentType, ...]:
        return self._component_type_collector()

    def add_component(self, type_name: str) -> EntityInspectorSnapshot:
        if self._entity is None:
            return self._snapshot
        self._execute(AddComponentCommand(self._entity, type_name))
        components = self._entity.tc_components
        self._selected_component = next(
            (
                index
                for index, component in enumerate(components)
                if component.type_name == type_name
            ),
            -1,
        )
        if self._selected_component >= 0:
            self.fields.set_targets((components[self._selected_component],))
            self._notify_component_selection(components[self._selected_component])
        else:
            self.fields.set_targets(())
            self._notify_component_selection(None)
        return self.refresh()

    def remove_selected_component(self) -> EntityInspectorSnapshot:
        entity = self._entity
        index = self._selected_component
        if entity is None or index < 0:
            return self._snapshot
        components = entity.tc_components
        if index < len(components):
            self._execute(RemoveComponentCommand(entity, components[index].type_name))
        else:
            soa_index = index - len(components)
            soa_names = entity.soa_component_names
            if soa_index < 0 or soa_index >= len(soa_names):
                _logger.error("Entity inspector selected component index is stale: %d", index)
                raise IndexError(index)
            self._execute(RemoveSoAComponentCommand(entity, soa_names[soa_index]))
        self._selected_component = -1
        self.fields.set_targets(())
        self._notify_component_selection(None)
        return self.refresh()

    def add_soa_component(self, type_name: str) -> EntityInspectorSnapshot:
        if self._entity is None:
            return self._snapshot
        self._execute(AddSoAComponentCommand(self._entity, type_name))
        self._selected_component = len(self._entity.tc_components) + list(
            self._entity.soa_component_names
        ).index(type_name)
        self.fields.set_targets(())
        self._notify_component_selection(None)
        return self.refresh()

    def _notify_component_selection(self, component_ref: object | None) -> None:
        if self._component_selection_changed is None:
            return
        try:
            self._component_selection_changed(self._entity, component_ref)
        except Exception:
            _logger.exception("Entity inspector component selection handler failed")
            raise

    def _reconcile_component_selection(self) -> None:
        entity = self._entity
        index = self._selected_component
        if entity is None or index < 0:
            return
        components = entity.tc_components
        total_count = len(components) + len(entity.soa_component_names)
        if index >= total_count:
            self._selected_component = -1
            self.fields.set_targets(())
            self._notify_component_selection(None)
            return
        if index >= len(components):
            if self.fields.targets:
                self.fields.set_targets(())
            return
        component = components[index]
        targets = self.fields.targets
        if (
            len(targets) != 1
            or not isinstance(targets[0], TcComponentRef)
            or not targets[0].valid
            or targets[0] != component
        ):
            self.fields.set_targets((component,))

    def _apply_component_field_change(
        self,
        field: InspectField,
        targets: tuple[object, ...],
        old_values: tuple[object, ...],
        value,
        merge: bool,
    ) -> None:
        if len(targets) != 1 or len(old_values) != 1:
            _logger.error(
                "Entity inspector expected one component edit target, got %d",
                len(targets),
            )
            raise RuntimeError("entity inspector component edit target count mismatch")
        command = ComponentFieldEditCommand(
            component=targets[0],
            field=field,
            old_value=old_values[0],
            new_value=value,
        )
        self._execute(command, merge=merge)

    def _execute(self, command: UndoCommand, *, merge: bool = False) -> None:
        if self._undo_handler is not None:
            self._undo_handler(command, merge)
        else:
            command.do()

    def _collect_descendants(self, entity: Entity, output: list[tuple[Entity, int]]) -> None:
        transform = entity.transform
        if transform is None:
            return
        for child_transform in transform.children:
            child = child_transform.entity
            if child is None:
                continue
            output.append((child, int(child.layer)))
            self._collect_descendants(child, output)

    def _build_snapshot(self) -> EntityInspectorSnapshot:
        entity = self._entity
        layer_names = tuple(self._layer_name(index) for index in range(64))
        if entity is None:
            return EntityInspectorSnapshot(
                entity=None,
                name="",
                uuid="",
                layer=-1,
                layer_names=layer_names,
                components=(),
                selected_component=-1,
                fields=self.fields.snapshot,
            )
        components = []
        for index, component in enumerate(entity.tc_components):
            display_name = component.get_field("display_name")
            type_name = component.type_name
            label = f"{display_name} ({type_name})" if display_name else type_name
            components.append(
                EntityInspectorComponent(
                    stable_id=f"component:{index}:{type_name}",
                    label=label,
                    type_name=type_name,
                )
            )
        for soa_name in entity.soa_component_names:
            components.append(
                EntityInspectorComponent(
                    stable_id=f"soa:{soa_name}",
                    label=f"[SoA] {soa_name}",
                    type_name=soa_name,
                    soa=True,
                )
            )
        return EntityInspectorSnapshot(
            entity=entity,
            name=entity.name or "",
            uuid=entity.uuid or "-",
            layer=int(entity.layer),
            layer_names=layer_names,
            components=tuple(components),
            selected_component=self._selected_component,
            fields=self.fields.snapshot,
        )

    def _layer_name(self, index: int) -> str:
        if self._scene is None:
            return f"Layer {index}"
        try:
            name = self._scene.get_layer_name(index)
        except Exception as error:
            _logger.error("Failed to read scene layer %d: %s", index, error)
            return f"Layer {index}"
        return name or f"Layer {index}"

__all__ = [
    "ComponentTypeCollector",
    "EntityInspectorComponent",
    "EntityInspectorComponentType",
    "ComponentSelectionHandler",
    "EntityInspectorController",
    "EntityInspectorSnapshot",
    "collect_component_types",
]
