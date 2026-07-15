"""Atomic prefab override metadata capture for editor undo commands."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from termin.prefab import (
    PrefabInstanceState,
    PrefabOverrideValue,
    PrefabStructuralOverride,
    PrefabStructuralOverrideKind,
    PrefabStructureReference,
    PrefabStructureReferenceKind,
)
from termin.scene import Component, Entity, TcComponentRef


_logger = logging.getLogger(__name__)


def _parent_entity(entity: Entity) -> Entity | None:
    parent = entity.transform.parent
    return parent.entity if parent is not None else None


def _state_on(entity: Entity) -> PrefabInstanceState | None:
    state = entity.get_component(PrefabInstanceState)
    return state if state is not None else None


def find_mapped_instance(entity: Entity) -> tuple[PrefabInstanceState, str] | None:
    """Return the nearest prefab state that owns ``entity`` as source structure."""
    current: Entity | None = entity
    while current is not None:
        state = _state_on(current)
        if state is not None:
            source_id = state.source_for_entity(entity)
            if source_id:
                return state, source_id
        current = _parent_entity(current)
    return None


def find_containing_instance(entity: Entity) -> PrefabInstanceState | None:
    """Return the nearest instance root containing mapped or local structure."""
    current: Entity | None = entity
    while current is not None:
        state = _state_on(current)
        if state is not None:
            return state
        current = _parent_entity(current)
    return None


@dataclass(frozen=True)
class PropertyOverrideSnapshot:
    value: PrefabOverrideValue | None
    target_kind: str | None


class PropertyOverrideCapture:
    def __init__(
        self,
        state: PrefabInstanceState,
        source_entity_id: str,
        source_component_id: str,
        field_path: str,
        target_kind: str,
    ) -> None:
        self.state = state
        self.source_entity_id = source_entity_id
        self.source_component_id = source_component_id
        self.field_path = field_path
        self.target_kind = target_kind
        previous = state.get_property_override(
            source_entity_id, source_component_id, field_path)
        previous_kind = state.get_property_override_kind(
            source_entity_id, source_component_id, field_path)
        self.previous = PropertyOverrideSnapshot(previous, previous_kind)

    def set(self, value: Any) -> None:
        encoded = PrefabOverrideValue.from_python(value, self.target_kind)
        self.state.set_property_override(
            self.source_entity_id,
            self.source_component_id,
            self.field_path,
            self.target_kind,
            encoded,
        )

    def restore(self) -> None:
        if self.previous.value is None:
            self.state.discard_property_override(
                self.source_entity_id, self.source_component_id, self.field_path)
            return
        if not self.previous.target_kind:
            _logger.error(
                "Prefab override snapshot has no target kind for entity=%s component=%s field=%s",
                self.source_entity_id,
                self.source_component_id,
                self.field_path,
            )
            raise RuntimeError("prefab override snapshot has no target kind")
        self.state.set_property_override(
            self.source_entity_id,
            self.source_component_id,
            self.field_path,
            self.previous.target_kind,
            self.previous.value,
        )


def capture_entity_property(
    entity: Entity, field_path: str, target_kind: str
) -> PropertyOverrideCapture | None:
    owner = find_mapped_instance(entity)
    if owner is None:
        return None
    state, source_entity_id = owner
    return PropertyOverrideCapture(
        state, source_entity_id, "", field_path, target_kind)


def capture_component_property(
    component: Component | TcComponentRef, field_path: str, target_kind: str
) -> PropertyOverrideCapture | None:
    entity = component.entity
    if entity is None or not entity.valid:
        return None
    owner = find_mapped_instance(entity)
    if owner is None:
        return None
    state, source_entity_id = owner
    source_component_id = state.source_for_component(entity, component.source_id)
    if not source_component_id:
        return None
    return PropertyOverrideCapture(
        state,
        source_entity_id,
        source_component_id,
        field_path,
        target_kind,
    )


def _clone_reference(source: PrefabStructureReference) -> PrefabStructureReference:
    result = PrefabStructureReference()
    result.kind = source.kind
    result.source_id = source.source_id
    result.local_entity = source.local_entity
    result.local_component_source_id = source.local_component_source_id
    return result


def _clone_structural_override(
    source: PrefabStructuralOverride | None,
) -> PrefabStructuralOverride | None:
    if source is None:
        return None
    result = PrefabStructuralOverride()
    result.kind = source.kind
    result.source_entity_id = source.source_entity_id
    result.source_component_id = source.source_component_id
    result.parent = _clone_reference(source.parent)
    result.before = _clone_reference(source.before)
    return result


class StructuralOverrideCapture:
    def __init__(
        self,
        state: PrefabInstanceState,
        kind: PrefabStructuralOverrideKind,
        source_id: str,
    ) -> None:
        self.state = state
        self.kind = kind
        self.source_id = source_id
        self.previous = _clone_structural_override(
            state.get_structural_override(kind, source_id))

    def set(self, item: PrefabStructuralOverride) -> None:
        self.state.set_structural_override(item)

    def restore(self) -> None:
        if self.previous is None:
            self.state.discard_structural_override(self.kind, self.source_id)
        else:
            self.state.set_structural_override(self.previous)


@dataclass(frozen=True)
class EntityMappingSnapshot:
    source_id: str
    runtime_uuid: str


@dataclass(frozen=True)
class ComponentMappingSnapshot:
    source_id: str
    runtime_owner_uuid: str


class EntitySuppressionCapture(StructuralOverrideCapture):
    def __init__(self, state: PrefabInstanceState, entity: Entity, source_id: str) -> None:
        super().__init__(state, PrefabStructuralOverrideKind.SUPPRESS_ENTITY, source_id)
        self.mappings: list[EntityMappingSnapshot] = []
        self.component_mappings: list[ComponentMappingSnapshot] = []
        self._collect_mappings(entity)

    def _collect_mappings(self, entity: Entity) -> None:
        source_id = self.state.source_for_entity(entity)
        if source_id:
            self.mappings.append(EntityMappingSnapshot(source_id, entity.uuid))
        for component in entity.tc_components:
            component_source_id = self.state.source_for_component(
                entity, component.source_id)
            if component_source_id:
                self.component_mappings.append(ComponentMappingSnapshot(
                    component_source_id, entity.uuid))
        for child_transform in entity.transform.children:
            child = child_transform.entity
            if child is not None:
                self._collect_mappings(child)

    def suppress(self) -> None:
        item = PrefabStructuralOverride()
        item.kind = PrefabStructuralOverrideKind.SUPPRESS_ENTITY
        item.source_entity_id = self.source_id
        self.set(item)

    def rebind_restored_mappings(self, scene) -> None:
        for mapping in self.mappings:
            entity = scene.get_entity(mapping.runtime_uuid)
            if entity is None or not entity.valid():
                _logger.error(
                    "Restored prefab entity uuid=%s for source=%s is unavailable",
                    mapping.runtime_uuid,
                    mapping.source_id,
                )
                raise RuntimeError("restored prefab entity mapping is unavailable")
            self.state.rebind_entity_mapping(mapping.source_id, entity)
        for mapping in self.component_mappings:
            owner = scene.get_entity(mapping.runtime_owner_uuid)
            if owner is None or not owner.valid():
                _logger.error(
                    "Restored prefab component owner uuid=%s for source=%s is unavailable",
                    mapping.runtime_owner_uuid,
                    mapping.source_id,
                )
                raise RuntimeError("restored prefab component owner is unavailable")
            self.state.rebind_component_mapping(mapping.source_id, owner)


def capture_entity_suppression(entity: Entity) -> EntitySuppressionCapture | None:
    owner = find_mapped_instance(entity)
    if owner is None:
        return None
    state, source_id = owner
    if state.entity == entity:
        return None
    return EntitySuppressionCapture(state, entity, source_id)


def capture_component_suppression(
    component: TcComponentRef,
) -> StructuralOverrideCapture | None:
    entity = component.entity
    if entity is None or not entity.valid:
        return None
    owner = find_mapped_instance(entity)
    if owner is None:
        return None
    state, _ = owner
    source_id = state.source_for_component(entity, component.source_id)
    if not source_id:
        return None
    return StructuralOverrideCapture(
        state, PrefabStructuralOverrideKind.SUPPRESS_COMPONENT, source_id)


def suppress_component(capture: StructuralOverrideCapture) -> None:
    item = PrefabStructuralOverride()
    item.kind = PrefabStructuralOverrideKind.SUPPRESS_COMPONENT
    item.source_component_id = capture.source_id
    capture.set(item)


def _entity_reference(
    state: PrefabInstanceState, entity: Entity | None, *, allow_end: bool
) -> PrefabStructureReference:
    result = PrefabStructureReference()
    if entity is None:
        if not allow_end:
            raise ValueError("prefab entity placement parent must be inside the instance")
        result.kind = PrefabStructureReferenceKind.END
        return result
    source_id = state.source_for_entity(entity)
    if source_id:
        result.kind = PrefabStructureReferenceKind.SOURCE
        result.source_id = source_id
        return result
    containing = find_containing_instance(entity)
    if containing is not state:
        raise ValueError("prefab placement reference is outside the instance")
    result.kind = PrefabStructureReferenceKind.LOCAL
    result.local_entity = entity
    return result


def capture_entity_placement(
    entity: Entity,
) -> StructuralOverrideCapture | None:
    owner = find_mapped_instance(entity)
    if owner is None:
        return None
    state, source_id = owner
    if state.entity == entity:
        return None
    return StructuralOverrideCapture(
        state, PrefabStructuralOverrideKind.PLACE_ENTITY, source_id)


def place_entity_from_live_state(
    capture: StructuralOverrideCapture, entity: Entity
) -> None:
    parent = _parent_entity(entity)
    siblings = [
        child.entity
        for child in parent.transform.children
        if child.entity is not None
    ] if parent is not None else []
    next_entity: Entity | None = None
    index = int(entity.sibling_index)
    if index + 1 < len(siblings):
        next_entity = siblings[index + 1]
    item = PrefabStructuralOverride()
    item.kind = PrefabStructuralOverrideKind.PLACE_ENTITY
    item.source_entity_id = capture.source_id
    item.parent = _entity_reference(capture.state, parent, allow_end=False)
    item.before = _entity_reference(capture.state, next_entity, allow_end=True)
    capture.set(item)
