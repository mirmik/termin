"""Toolkit-neutral production scene hierarchy state and actions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from termin.editor_core.dialog_service import DialogService
from termin.editor_core.editor_commands import EntityPropertyEditCommand
from termin.editor_core.entity_operations import EntityOperations
from termin.editor_core.undo_stack import UndoCommand
from termin.scene import Entity


_logger = logging.getLogger(__name__)
_MODEL_EXTENSIONS = (".glb", ".gltf")
_EXTERNAL_EXTENSIONS = _MODEL_EXTENSIONS + (".prefab",)


@dataclass(frozen=True)
class SceneHierarchyNode:
    stable_id: str
    name: str
    parent_id: str | None
    visible: bool
    enabled: bool
    component_count: int

    @property
    def subtitle(self) -> str:
        state = []
        if not self.visible:
            state.append("hidden")
        if not self.enabled:
            state.append("disabled")
        if self.component_count:
            state.append(f"{self.component_count} components")
        return ", ".join(state)


@dataclass(frozen=True)
class SceneHierarchySnapshot:
    nodes: tuple[SceneHierarchyNode, ...]
    selected_id: str | None
    expanded_ids: frozenset[str]
    revision: int

    @property
    def status(self) -> str:
        return f"Scene entities: {len(self.nodes)}"


@dataclass(frozen=True)
class SceneHierarchyAction:
    stable_id: str
    label: str
    enabled: bool = True


class SceneHierarchyController:
    def __init__(
        self,
        scene,
        *,
        undo_handler: Callable[[UndoCommand, bool], None],
        dialog_service: DialogService,
        on_object_selected: Callable[[object | None], None],
        request_viewport_update: Callable[[], None] | None = None,
        on_snapshot_changed: Callable[[SceneHierarchySnapshot], None] | None = None,
    ) -> None:
        self._scene = scene
        self._on_object_selected = on_object_selected
        self._request_viewport_update = request_viewport_update
        self._undo_handler = undo_handler
        self._on_snapshot_changed = on_snapshot_changed
        self._expanded_ids: set[str] = set()
        self._selected_id: str | None = None
        self._entities: dict[str, Entity] = {}
        self._nodes: tuple[SceneHierarchyNode, ...] = ()
        self._revision = 0
        self._ops = EntityOperations(
            scene=scene,
            undo_handler=undo_handler,
            dialog_service=dialog_service,
            view=self,
            request_viewport_update=request_viewport_update,
        )
        self.rebuild()

    @property
    def operations(self) -> EntityOperations:
        return self._ops

    def set_snapshot_changed_handler(
        self,
        handler: Callable[[SceneHierarchySnapshot], None] | None,
    ) -> None:
        self._on_snapshot_changed = handler

    def _publish(self, snapshot: SceneHierarchySnapshot) -> SceneHierarchySnapshot:
        if self._on_snapshot_changed is not None:
            self._on_snapshot_changed(snapshot)
        return snapshot

    def set_scene(self, scene) -> SceneHierarchySnapshot:
        self._scene = scene
        self._ops.set_scene(scene)
        self._selected_id = None
        self._expanded_ids.clear()
        return self.rebuild()

    def rebuild(self, select_obj: object | None = None) -> SceneHierarchySnapshot:
        self._entities.clear()
        nodes: list[SceneHierarchyNode] = []
        if self._scene is not None:
            self._append_entities(nodes, None, list(self._scene.root_entities))
        self._nodes = tuple(nodes)
        live_ids = set(self._entities)
        self._expanded_ids.intersection_update(live_ids)
        if self._selected_id not in live_ids:
            self._selected_id = None
        self._revision += 1
        if select_obj is not None:
            stable_id = self._entity_id(select_obj) if isinstance(select_obj, Entity) else None
            if stable_id in self._entities:
                return self.select_id(stable_id)
        return self._publish(self.snapshot())

    def _append_entities(
        self,
        nodes: list[SceneHierarchyNode],
        parent_id: str | None,
        entities: list[Entity],
    ) -> None:
        for entity in entities:
            stable_id = self._entity_id(entity)
            if stable_id is None:
                _logger.error("Scene hierarchy skipped entity without UUID: %s", entity.name)
                continue
            self._entities[stable_id] = entity
            nodes.append(
                SceneHierarchyNode(
                    stable_id=stable_id,
                    name=entity.name or "(unnamed)",
                    parent_id=parent_id,
                    visible=bool(entity.visible),
                    enabled=bool(entity.enabled),
                    component_count=len(entity.tc_components),
                )
            )
            children = [
                transform.entity
                for transform in entity.transform.children
                if transform.entity is not None
            ]
            self._append_entities(
                nodes,
                stable_id,
                children,
            )

    @staticmethod
    def _entity_id(entity: Entity | None) -> str | None:
        if entity is None or not entity.uuid:
            return None
        return entity.uuid

    def snapshot(self) -> SceneHierarchySnapshot:
        return SceneHierarchySnapshot(
            nodes=self._nodes,
            selected_id=self._selected_id,
            expanded_ids=frozenset(self._expanded_ids),
            revision=self._revision,
        )

    def entity_for_id(self, stable_id: str | None) -> Entity | None:
        return self._entities.get(stable_id) if stable_id is not None else None

    def select_id(self, stable_id: str | None) -> SceneHierarchySnapshot:
        if stable_id is not None and stable_id not in self._entities:
            _logger.error("Scene hierarchy selection references unknown entity: %s", stable_id)
            raise KeyError(stable_id)
        self._selected_id = stable_id
        self._expand_selected_ancestors()
        self._revision += 1
        self._on_object_selected(self.entity_for_id(stable_id))
        return self._publish(self.snapshot())

    def select_object(self, obj: object | None) -> SceneHierarchySnapshot:
        if not isinstance(obj, Entity):
            return self.select_id(None)
        stable_id = self._entity_id(obj)
        if stable_id not in self._entities:
            return self.rebuild(select_obj=obj)
        return self.select_id(stable_id)

    def _expand_selected_ancestors(self) -> None:
        entity = self.entity_for_id(self._selected_id)
        parent = entity.transform.parent.entity if entity is not None and entity.transform.parent else None
        while parent is not None:
            parent_id = self._entity_id(parent)
            if parent_id is not None:
                self._expanded_ids.add(parent_id)
            parent = parent.transform.parent.entity if parent.transform.parent else None

    def set_expanded(self, stable_id: str, expanded: bool) -> SceneHierarchySnapshot:
        if stable_id not in self._entities:
            raise KeyError(stable_id)
        if expanded:
            self._expanded_ids.add(stable_id)
        else:
            self._expanded_ids.discard(stable_id)
        self._revision += 1
        return self._publish(self.snapshot())

    def collapse_all(self) -> SceneHierarchySnapshot:
        self._expanded_ids.clear()
        self._revision += 1
        return self._publish(self.snapshot())

    def get_expanded_entity_uuids(self) -> list[str]:
        return sorted(self._expanded_ids)

    def set_expanded_entity_uuids(self, uuids: list[str]) -> SceneHierarchySnapshot:
        self._expanded_ids = set(uuids).intersection(self._entities)
        self._revision += 1
        return self._publish(self.snapshot())

    def context_actions(self, stable_id: str | None) -> tuple[SceneHierarchyAction, ...]:
        entity = self.entity_for_id(stable_id)
        if entity is None:
            return (SceneHierarchyAction("create-root", "Add Entity"),)
        return (
            SceneHierarchyAction("create-child", "Add Child Entity"),
            SceneHierarchyAction("rename", "Rename..."),
            SceneHierarchyAction("duplicate", "Duplicate"),
            SceneHierarchyAction(
                "toggle-visible",
                "Hide" if entity.visible else "Show",
            ),
            SceneHierarchyAction("delete", "Delete"),
            SceneHierarchyAction("create-root", "Add Root Entity"),
        )

    def execute_context_action(
        self,
        action_id: str,
        stable_id: str | None,
    ) -> SceneHierarchySnapshot:
        entity = self.entity_for_id(stable_id)
        if action_id == "create-root":
            self._ops.create_entity(None)
        elif action_id == "create-child" and entity is not None:
            self._ops.create_entity(entity)
        elif action_id == "rename" and entity is not None:
            self._ops.rename_entity(entity)
        elif action_id == "duplicate" and entity is not None:
            self._ops.duplicate_entity(entity)
        elif action_id == "delete" and entity is not None:
            self._ops.delete_entity(entity)
        elif action_id == "toggle-visible" and entity is not None:
            command = EntityPropertyEditCommand(
                entity,
                "visible",
                bool(entity.visible),
                not bool(entity.visible),
                text=f"{'Hide' if entity.visible else 'Show'} entity '{entity.name}'",
            )
            self._undo_handler(command, False)
            self.update_entity(entity)
            if self._request_viewport_update is not None:
                self._request_viewport_update()
        else:
            _logger.error("Invalid scene hierarchy action %s for %s", action_id, stable_id)
            raise ValueError(f"invalid scene hierarchy action: {action_id}")
        return self._publish(self.snapshot())

    def drop_entity(
        self,
        dragged_id: str,
        target_id: str | None,
        position: str,
    ) -> SceneHierarchySnapshot:
        dragged = self.entity_for_id(dragged_id)
        target = self.entity_for_id(target_id)
        if dragged is None:
            raise KeyError(dragged_id)
        if position not in ("root", "inside", "before", "after"):
            raise ValueError(f"invalid scene hierarchy drop position: {position}")
        if position == "inside":
            new_parent = target
        elif position == "root" or target is None:
            new_parent = None
        else:
            parent_transform = target.transform.parent if target.transform is not None else None
            new_parent = parent_transform.entity if parent_transform is not None else None
        if new_parent is dragged or self._is_descendant(new_parent, dragged):
            _logger.error("Scene hierarchy rejected cyclic drop of %s", dragged_id)
            raise ValueError("scene hierarchy drop would create a cycle")

        sibling_ids = self._sibling_ids(new_parent)
        if dragged_id in sibling_ids:
            sibling_ids.remove(dragged_id)
        if position in ("before", "after") and target_id in sibling_ids:
            index = sibling_ids.index(target_id)
            if position == "after":
                index += 1
            sibling_ids.insert(index, dragged_id)
        else:
            sibling_ids.append(dragged_id)
        self._ops.reparent_entity(
            dragged,
            new_parent,
            sibling_index=sibling_ids.index(dragged_id),
        )
        return self.snapshot()

    @staticmethod
    def _is_descendant(candidate: Entity | None, ancestor: Entity) -> bool:
        current = candidate
        while current is not None:
            if current.uuid == ancestor.uuid:
                return True
            parent = current.transform.parent if current.transform is not None else None
            current = parent.entity if parent is not None else None
        return False

    def _sibling_ids(self, parent: Entity | None) -> list[str]:
        if parent is None:
            entities = list(self._scene.root_entities)
        else:
            entities = [
                transform.entity
                for transform in parent.transform.children
                if transform.entity is not None
            ]
        return [stable_id for entity in entities if (stable_id := self._entity_id(entity)) is not None]

    def can_drop_project_file(self, extension: str) -> bool:
        return extension.casefold() in _EXTERNAL_EXTENSIONS

    def drop_project_file(
        self,
        path: str,
        extension: str,
        target_id: str | None,
        position: str,
    ) -> SceneHierarchySnapshot:
        normalized = extension.casefold()
        if not self.can_drop_project_file(normalized):
            raise ValueError(f"unsupported scene hierarchy file drop: {extension}")
        if position not in ("root", "inside", "before", "after"):
            raise ValueError(f"invalid scene hierarchy drop position: {position}")
        target = self.entity_for_id(target_id)
        if position == "inside":
            parent = target
        elif position in ("before", "after") and target is not None:
            parent_transform = target.transform.parent if target.transform is not None else None
            parent = parent_transform.entity if parent_transform is not None else None
        else:
            parent = None
        if normalized in _MODEL_EXTENSIONS:
            self._ops.drop_glb(path, parent)
        else:
            self._ops.drop_prefab(path, parent)
        return self.snapshot()

    # EntityOperations view surface. Rebuilding keeps every frontend projection consistent.
    def add_entity(self, entity: Entity) -> None:
        self.rebuild(select_obj=entity)

    def add_entity_hierarchy(self, entity: Entity) -> None:
        self.rebuild(select_obj=entity)

    def remove_entity(self, entity: Entity, select_parent: bool = True) -> None:
        parent = None
        if select_parent and entity.valid() and entity.transform is not None and entity.transform.parent:
            parent = entity.transform.parent.entity
        self.rebuild(select_obj=parent if select_parent else None)

    def move_entity(self, entity: Entity, new_parent: Entity | None) -> None:
        self.rebuild(select_obj=entity)

    def update_entity(self, entity: Entity) -> None:
        self.rebuild(select_obj=entity)


__all__ = [
    "SceneHierarchyAction",
    "SceneHierarchyController",
    "SceneHierarchyNode",
    "SceneHierarchySnapshot",
]
