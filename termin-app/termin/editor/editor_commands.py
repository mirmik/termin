from __future__ import annotations

import copy
import logging
from typing import Any

import numpy as np

from termin.editor.undo_stack import UndoCommand
from termin.geombase import GeneralPose3
from termin.kinematic.general_transform import GeneralTransform3
from termin.visualization.core.entity import Entity, Component
from termin.entity import TcComponentRef
from termin.editor.inspect_field import InspectField


_logger = logging.getLogger(__name__)


def _clone_pose(pose: GeneralPose3) -> GeneralPose3:
    """
    Создаёт независимую копию позы.

    Массивы угла и смещения копируются, чтобы последующие
    изменения позы не портили снимок для undo/redo.
    """
    return GeneralPose3(ang=pose.ang.copy(), lin=pose.lin.copy(), scale=pose.scale.copy())


def _clone_value(value: Any) -> Any:
    """
    Создаёт "безопасную" копию значения для хранения в команде.

    Для numpy-матриц и numpy-векторов (модуль numpy)
    делается copy(), для остальных типов возвращается как есть.
    """
    if isinstance(value, np.ndarray):
        return value.copy()
    return value


def _entity_is_valid(entity: Entity | None) -> bool:
    return entity is not None and entity.valid()


def _entity_uuid(entity: Entity | None) -> str | None:
    if entity is None:
        return None
    uuid = entity.uuid
    return uuid if uuid else None


def _transform_entity(transform: GeneralTransform3 | None) -> Entity | None:
    if transform is None:
        return None
    return transform.entity


def _transform_entity_uuid(transform: GeneralTransform3 | None) -> str | None:
    return _entity_uuid(_transform_entity(transform))


def _component_entity(component: Component | TcComponentRef | None) -> Entity | None:
    if component is None:
        return None
    return component.entity


def _component_type_name(component: Component | TcComponentRef) -> str:
    if isinstance(component, TcComponentRef):
        return component.type_name
    return component.type_name()


def _snapshot_entity(entity: Entity) -> dict:
    data = entity.serialize()
    if data is None:
        _logger.error("Failed to serialize entity '%s' for undo command", entity.name)
        raise RuntimeError(f"Failed to serialize entity '{entity.name}' for undo command")
    return copy.deepcopy(data)


def _resolve_scene_entity(scene, uuid: str | None) -> Entity | None:
    if uuid is None:
        return None
    try:
        entity = scene.get_entity(uuid)
    except Exception:
        _logger.exception("Failed to resolve entity uuid=%s for undo command", uuid)
        raise
    if entity is None:
        _logger.warning("Entity uuid=%s not found while applying undo command", uuid)
        return None
    return entity


def _resolve_parent_transform(scene, parent_uuid: str | None) -> GeneralTransform3 | None:
    parent = _resolve_scene_entity(scene, parent_uuid)
    if parent is None:
        return None
    return parent.transform


def _resolve_command_entity(scene, uuid: str | None, command_text: str) -> Entity:
    entity = _resolve_scene_entity(scene, uuid)
    if entity is None:
        _logger.error("Failed to resolve entity uuid=%s while applying undo command '%s'", uuid, command_text)
        raise RuntimeError(f"Failed to resolve entity uuid={uuid}")
    return entity


def _resolve_command_transform(scene, uuid: str | None, command_text: str) -> GeneralTransform3:
    return _resolve_command_entity(scene, uuid, command_text).transform


def _resolve_command_component(
    scene,
    entity_uuid: str | None,
    type_name: str,
    command_text: str,
) -> TcComponentRef:
    entity = _resolve_command_entity(scene, entity_uuid, command_text)
    ref = entity.get_tc_component(type_name)
    if ref is None or not ref.valid:
        _logger.error(
            "Failed to resolve component '%s' on entity uuid=%s while applying undo command '%s'",
            type_name,
            entity_uuid,
            command_text,
        )
        raise RuntimeError(f"Failed to resolve component '{type_name}' on entity uuid={entity_uuid}")
    return ref


def _deserialize_entity_snapshot(
    scene,
    data: dict,
    parent_uuid: str | None,
    command_text: str,
    *,
    with_children: bool = False,
) -> Entity:
    payload = copy.deepcopy(data)
    if with_children:
        entity = Entity.deserialize_with_children(payload, context=None, scene=scene)
    else:
        entity = Entity.deserialize(payload, context=None, scene=scene)
    if entity is None or not entity.valid():
        name = data.get("name", "entity")
        _logger.error("Failed to restore entity '%s' while applying undo command '%s'", name, command_text)
        raise RuntimeError(f"Failed to restore entity '{name}'")

    parent_transform = _resolve_parent_transform(scene, parent_uuid)
    if parent_transform is not None:
        entity.transform.set_parent(parent_transform)
    return entity


def _remove_entity_tree(scene, entity: Entity) -> None:
    if entity.transform is not None:
        for child_transform in list(entity.transform.children):
            child = child_transform.entity
            if child is not None:
                _remove_entity_tree(scene, child)
    scene.remove(entity)


class TransformEditCommand(UndoCommand):
    """
    Команда изменения положения, ориентации и масштаба сущности
    через TransformInspector.

    Ожидается, что transform принадлежит entity.
    Масштаб хранится внутри GeneralPose3.
    """

    def __init__(
        self,
        transform: GeneralTransform3,
        old_pose: GeneralPose3,
        new_pose: GeneralPose3,
        text: str = "Transform change",
    ) -> None:
        super().__init__(text)
        entity = _transform_entity(transform)
        self._scene = entity.scene if entity is not None else None
        self._entity_uuid = _entity_uuid(entity)
        self._transform = transform
        self._old_pose = _clone_pose(old_pose)
        self._new_pose = _clone_pose(new_pose)

    @property
    def entity(self) -> Entity | None:
        if _entity_is_valid(_transform_entity(self._transform)):
            return _transform_entity(self._transform)
        if self._scene is None:
            return None
        return _resolve_scene_entity(self._scene, self._entity_uuid)

    def _current_transform(self) -> GeneralTransform3:
        if _entity_is_valid(_transform_entity(self._transform)):
            return self._transform
        if self._scene is None:
            _logger.error("TransformEditCommand has no scene for entity uuid=%s", self._entity_uuid)
            raise RuntimeError("TransformEditCommand has no scene")
        self._transform = _resolve_command_transform(self._scene, self._entity_uuid, self.text)
        return self._transform

    def do(self) -> None:
        self._current_transform().relocate(self._new_pose)

    def undo(self) -> None:
        self._current_transform().relocate(self._old_pose)

    def merge_with(self, other: UndoCommand) -> bool:
        """
        Склеивает серию мелких правок в одну команду.

        Старое состояние остаётся состоянием до первого изменения,
        новое состояние — после последнего изменения.
        """
        if not isinstance(other, TransformEditCommand):
            return False
        if other._entity_uuid != self._entity_uuid:
            return False

        self._new_pose = _clone_pose(other._new_pose)
        return True


class ComponentFieldEditCommand(UndoCommand):
    """
    Команда изменения значения одного поля компонента через инспектор.

    Работает с объектом InspectField, который сам знает,
    как читать и записывать значение в компонент.
    """

    def __init__(
        self,
        component: Component,
        field: InspectField,
        old_value: Any,
        new_value: Any,
        text: str = "Component field change",
    ) -> None:
        super().__init__(text)
        entity = _component_entity(component)
        self._scene = entity.scene if entity is not None else None
        self._entity_uuid = _entity_uuid(entity)
        self._component_type_name = _component_type_name(component)
        self._component = component
        self._field = field
        self._old_value = _clone_value(old_value)
        self._new_value = _clone_value(new_value)

    def _current_component(self) -> Component | TcComponentRef:
        if self._scene is not None:
            self._component = _resolve_command_component(
                self._scene,
                self._entity_uuid,
                self._component_type_name,
                self.text,
            )
            return self._component
        if isinstance(self._component, TcComponentRef) and self._component.valid:
            return self._component
        if isinstance(self._component, Component) and _entity_is_valid(self._component.entity):
            return self._component
        if self._scene is None:
            _logger.error(
                "ComponentFieldEditCommand has no scene for entity uuid=%s component=%s",
                self._entity_uuid,
                self._component_type_name,
            )
            raise RuntimeError("ComponentFieldEditCommand has no scene")
        raise RuntimeError("ComponentFieldEditCommand has no live component")

    def do(self) -> None:
        # При каждом применении берём копию, чтобы не делиться
        # внутренними массивами между командой и объектом.
        self._field.set_value(self._current_component(), _clone_value(self._new_value))

    def undo(self) -> None:
        self._field.set_value(self._current_component(), _clone_value(self._old_value))

    def merge_with(self, other: UndoCommand) -> bool:
        """
        Склейка последовательных правок одного и того же поля
        одного и того же компонента.
        """
        if not isinstance(other, ComponentFieldEditCommand):
            return False
        if other._entity_uuid != self._entity_uuid:
            return False
        if other._component_type_name != self._component_type_name:
            return False
        if other._field is not self._field:
            return False

        self._new_value = _clone_value(other._new_value)
        return True


class AddComponentCommand(UndoCommand):
    """
    Добавление компонента к сущности.

    Работает через TcComponentRef - не требует Python wrapper.
    Хранит type_name и сериализованные данные для redo.
    """

    def __init__(
        self,
        entity: Entity,
        type_name: str,
        ref: TcComponentRef | None = None,
        text: str = "Add component",
    ) -> None:
        super().__init__(text)
        self._entity = entity
        self._scene = entity.scene
        self._entity_uuid = _entity_uuid(entity)
        self._type_name = type_name
        self._ref = ref
        self._data: dict | None = None

    def _current_entity(self) -> Entity:
        if _entity_is_valid(self._entity):
            return self._entity
        self._entity = _resolve_command_entity(self._scene, self._entity_uuid, self.text)
        return self._entity

    def do(self) -> None:
        entity = self._current_entity()
        # Проверяем, есть ли уже компонент этого типа
        if entity.has_tc_component(self._type_name):
            self._ref = entity.get_tc_component(self._type_name)
            return

        # Создаём и добавляем компонент
        self._ref = entity.add_component_by_name(self._type_name)

        # Применяем сохранённые данные (при redo)
        if self._data is not None and self._ref.valid:
            self._ref.deserialize_data(self._data)

    def undo(self) -> None:
        entity = self._current_entity()
        self._ref = entity.get_tc_component(self._type_name)

        if self._ref is not None and self._ref.valid:
            # Сохраняем данные перед удалением (для redo)
            self._data = self._ref.serialize_data()
            entity.remove_component_ref(self._ref)
            self._ref = None


class RemoveComponentCommand(UndoCommand):
    """
    Удаление компонента из сущности.

    Работает через TcComponentRef - не требует Python wrapper.
    Хранит type_name и сериализованные данные для undo.
    """

    def __init__(
        self,
        entity: Entity,
        type_name: str,
        text: str = "Remove component",
    ) -> None:
        super().__init__(text)
        self._entity = entity
        self._scene = entity.scene
        self._entity_uuid = _entity_uuid(entity)
        self._type_name = type_name
        self._data: dict | None = None

    def _current_entity(self) -> Entity:
        if _entity_is_valid(self._entity):
            return self._entity
        self._entity = _resolve_command_entity(self._scene, self._entity_uuid, self.text)
        return self._entity

    def do(self) -> None:
        entity = self._current_entity()
        ref = entity.get_tc_component(self._type_name)
        if ref is not None and ref.valid:
            # Сохраняем данные перед удалением (для undo)
            self._data = ref.serialize_data()
            entity.remove_component_ref(ref)

    def undo(self) -> None:
        entity = self._current_entity()
        # Проверяем, что компонента нет
        if entity.has_tc_component(self._type_name):
            return

        # Создаём компонент заново
        ref = entity.add_component_by_name(self._type_name)

        # Восстанавливаем данные
        if self._data is not None and ref.valid:
            ref.deserialize_data(self._data)


class AddEntityCommand(UndoCommand):
    """
    Добавление сущности в сцену.

    В do() сущность добавляется, в undo() — удаляется.
    """

    def __init__(
        self,
        scene,
        entity: Entity,
        parent_transform: GeneralTransform3 | None = None,
        text: str = "Add entity",
    ) -> None:
        super().__init__(text)
        self._scene = scene
        self._entity = entity
        self._entity_uuid = _entity_uuid(entity)
        effective_parent_transform = parent_transform
        if effective_parent_transform is None:
            effective_parent_transform = entity.transform.parent
        self._parent_uuid = _transform_entity_uuid(effective_parent_transform)
        self._serialized_data = _snapshot_entity(entity)

    @property
    def entity(self) -> Entity | None:
        return self._entity

    @property
    def parent_entity(self) -> Entity | None:
        return _resolve_scene_entity(self._scene, self._parent_uuid)

    def do(self) -> None:
        if _entity_is_valid(self._entity):
            parent_transform = _resolve_parent_transform(self._scene, self._parent_uuid)
            if parent_transform is not None:
                self._entity.transform.set_parent(parent_transform)
            self._entity = self._scene.add(self._entity)
        else:
            self._entity = _deserialize_entity_snapshot(
                self._scene,
                self._serialized_data,
                self._parent_uuid,
                self.text,
            )
        self._entity_uuid = _entity_uuid(self._entity)

    def undo(self) -> None:
        entity = self._entity
        if not _entity_is_valid(entity):
            entity = _resolve_scene_entity(self._scene, self._entity_uuid)
        if entity is None:
            _logger.warning("AddEntityCommand.undo: entity uuid=%s is already absent", self._entity_uuid)
            return
        self._serialized_data = _snapshot_entity(entity)
        self._scene.remove(entity)
        self._entity = None


class DeleteEntityCommand(UndoCommand):
    """
    Удаление сущности из сцены.

    В do() сущность удаляется, в undo() — добавляется обратно.
    """

    def __init__(
        self,
        scene,
        entity: Entity,
        text: str = "Delete entity",
    ) -> None:
        super().__init__(text)
        self._scene = scene
        self._entity = entity
        self._entity_uuid = _entity_uuid(entity)
        self._parent_uuid = _transform_entity_uuid(entity.transform.parent)
        self._serialized_data = _snapshot_entity(entity)

    @property
    def entity(self) -> Entity | None:
        return self._entity

    @property
    def parent_entity(self) -> Entity | None:
        return _resolve_scene_entity(self._scene, self._parent_uuid)

    def do(self) -> None:
        entity = self._entity
        if not _entity_is_valid(entity):
            entity = _resolve_scene_entity(self._scene, self._entity_uuid)
        if entity is None:
            _logger.warning("DeleteEntityCommand.do: entity uuid=%s is already absent", self._entity_uuid)
            return
        self._serialized_data = _snapshot_entity(entity)
        _remove_entity_tree(self._scene, entity)
        self._entity = None

    def undo(self) -> None:
        self._entity = _deserialize_entity_snapshot(
            self._scene,
            self._serialized_data,
            self._parent_uuid,
            self.text,
            with_children=True,
        )
        self._entity_uuid = _entity_uuid(self._entity)


class ReparentEntityCommand(UndoCommand):
    """
    Перемещение сущности к другому родителю (drag-drop в SceneTree).

    В do() сущность перемещается к новому родителю,
    в undo() — возвращается к старому.

    Global pose сохраняется: local pose пересчитывается так,
    чтобы объект остался на том же месте в мире.
    """

    def __init__(
        self,
        entity: Entity,
        old_parent: GeneralTransform3 | None,
        new_parent: GeneralTransform3 | None,
        text: str | None = None,
    ) -> None:
        if text is None:
            old_name = old_parent.entity.name if old_parent and old_parent.entity else "root"
            new_name = new_parent.entity.name if new_parent and new_parent.entity else "root"
            text = f"Reparent '{entity.name}' from '{old_name}' to '{new_name}'"
        super().__init__(text)
        self._scene = entity.scene
        self._entity = entity
        self._entity_uuid = _entity_uuid(entity)
        self._old_parent_uuid = _transform_entity_uuid(old_parent)
        self._new_parent_uuid = _transform_entity_uuid(new_parent)
        # Сохраняем local pose для undo
        self._old_local_pose = _clone_pose(entity.transform.local_pose())

    @property
    def entity(self) -> Entity | None:
        if _entity_is_valid(self._entity):
            return self._entity
        return _resolve_scene_entity(self._scene, self._entity_uuid)

    def _current_entity(self) -> Entity:
        if _entity_is_valid(self._entity):
            return self._entity
        self._entity = _resolve_command_entity(self._scene, self._entity_uuid, self.text)
        return self._entity

    def do(self) -> None:
        entity = self._current_entity()
        # Сохраняем global pose до смены родителя
        global_pose = entity.transform.global_pose()
        # Меняем родителя
        entity.transform.set_parent(_resolve_parent_transform(self._scene, self._new_parent_uuid))
        # Восстанавливаем global pose (пересчитывает local pose)
        entity.transform.relocate_global(global_pose)

    def undo(self) -> None:
        entity = self._current_entity()
        # Возвращаем родителя и восстанавливаем оригинальный local pose
        entity.transform.set_parent(_resolve_parent_transform(self._scene, self._old_parent_uuid))
        entity.transform.relocate(self._old_local_pose)


__all__ = [
    "TransformEditCommand",
    "ComponentFieldEditCommand",
    "AddComponentCommand",
    "RemoveComponentCommand",
    "AddEntityCommand",
    "DeleteEntityCommand",
    "ReparentEntityCommand",
    "RenameEntityCommand",
    "DuplicateEntityCommand",
]


class RenameEntityCommand(UndoCommand):
    """
    Переименование сущности.

    В do() устанавливается новое имя, в undo() — старое.
    """

    def __init__(
        self,
        entity: Entity,
        old_name: str,
        new_name: str,
        text: str | None = None,
    ) -> None:
        if text is None:
            text = f"Rename entity '{old_name}' to '{new_name}'"
        super().__init__(text)
        self._entity = entity
        self._scene = entity.scene
        self._entity_uuid = _entity_uuid(entity)
        self._old_name = old_name
        self._new_name = new_name

    @property
    def entity(self) -> Entity | None:
        if _entity_is_valid(self._entity):
            return self._entity
        return _resolve_scene_entity(self._scene, self._entity_uuid)

    def _current_entity(self) -> Entity:
        if _entity_is_valid(self._entity):
            return self._entity
        self._entity = _resolve_command_entity(self._scene, self._entity_uuid, self.text)
        return self._entity

    def do(self) -> None:
        self._current_entity().name = self._new_name

    def undo(self) -> None:
        self._current_entity().name = self._old_name

    def merge_with(self, other: UndoCommand) -> bool:
        """
        Склейка последовательных переименований одной и той же сущности.
        """
        if not isinstance(other, RenameEntityCommand):
            return False
        if other._entity_uuid != self._entity_uuid:
            return False

        self._new_name = other._new_name
        self.text = other.text
        return True


class DuplicateEntityCommand(UndoCommand):
    """
    Дублирование сущности.

    В do() создаётся копия через scene, в undo() — удаляется.
    """

    def __init__(
        self,
        scene,
        source_entity: Entity,
        text: str | None = None,
    ) -> None:
        if text is None:
            text = f"Duplicate '{source_entity.name}'"
        super().__init__(text)
        self._scene = scene
        self._source_name = source_entity.name
        self._parent_uuid = _transform_entity_uuid(source_entity.transform.parent)
        self._copy: Entity | None = None

        # Serialize source for do/redo
        self._serialized_data = _snapshot_entity(source_entity)
        self._remove_uuids_recursive(self._serialized_data)

    @property
    def entity(self) -> Entity | None:
        """The duplicated entity (available after do())."""
        return self._copy

    def _remove_uuids_recursive(self, data: dict) -> None:
        """Remove uuid fields to force new UUID generation."""
        data.pop("uuid", None)
        data.pop("instance_uuid", None)
        for child in data.get("children", []):
            self._remove_uuids_recursive(child)
        for child in data.get("added_children", []):
            self._remove_uuids_recursive(child)

    def do(self) -> None:
        # Deserialize directly into scene's pool
        self._copy = Entity.deserialize(
            copy.deepcopy(self._serialized_data), context=None, scene=self._scene
        )
        if self._copy is None or not self._copy.valid():
            _logger.error("Failed to duplicate entity '%s'", self._source_name)
            raise RuntimeError(f"Failed to duplicate entity '{self._source_name}'")
        self._copy.name = f"{self._source_name}_copy"

        # Set parent
        parent_transform = _resolve_parent_transform(self._scene, self._parent_uuid)
        if parent_transform is not None:
            self._copy.transform.set_parent(parent_transform)

    def undo(self) -> None:
        if self._copy is not None:
            self._scene.remove(self._copy)
            self._copy = None
