from __future__ import annotations

from typing import Any

import numpy as np

from termin.editor.undo_stack import UndoCommand
from termin.geombase import GeneralPose3
from termin.kinematic.general_transform import GeneralTransform3
from termin.visualization.core.entity import Entity, Component
from termin.entity import TcComponentRef
from termin.editor.inspect_field import InspectField


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
        self._transform = transform
        self._old_pose = _clone_pose(old_pose)
        self._new_pose = _clone_pose(new_pose)

    def do(self) -> None:
        self._transform.relocate(self._new_pose)

    def undo(self) -> None:
        self._transform.relocate(self._old_pose)

    def merge_with(self, other: UndoCommand) -> bool:
        """
        Склеивает серию мелких правок в одну команду.

        Старое состояние остаётся состоянием до первого изменения,
        новое состояние — после последнего изменения.
        """
        if not isinstance(other, TransformEditCommand):
            return False
        if other._transform is not self._transform:
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
        self._component = component
        self._field = field
        self._old_value = _clone_value(old_value)
        self._new_value = _clone_value(new_value)

    def do(self) -> None:
        # При каждом применении берём копию, чтобы не делиться
        # внутренними массивами между командой и объектом.
        self._field.set_value(self._component, _clone_value(self._new_value))

    def undo(self) -> None:
        self._field.set_value(self._component, _clone_value(self._old_value))

    def merge_with(self, other: UndoCommand) -> bool:
        """
        Склейка последовательных правок одного и того же поля
        одного и того же компонента.
        """
        if not isinstance(other, ComponentFieldEditCommand):
            return False
        if other._component is not self._component:
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
        self._type_name = type_name
        self._ref = ref
        self._data: dict | None = None

    def do(self) -> None:
        # Проверяем, есть ли уже компонент этого типа
        if self._entity.has_tc_component(self._type_name):
            return

        # Создаём и добавляем компонент
        self._ref = self._entity.add_component_by_name(self._type_name)

        # Применяем сохранённые данные (при redo)
        if self._data is not None and self._ref.valid:
            self._ref.deserialize_data(self._data)

    def undo(self) -> None:
        if self._ref is None or not self._ref.valid:
            self._ref = self._entity.get_tc_component(self._type_name)

        if self._ref is not None and self._ref.valid:
            # Сохраняем данные перед удалением (для redo)
            self._data = self._ref.serialize_data()
            self._entity.remove_component_ref(self._ref)
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
        self._type_name = type_name
        self._data: dict | None = None

    def do(self) -> None:
        ref = self._entity.get_tc_component(self._type_name)
        if ref is not None and ref.valid:
            # Сохраняем данные перед удалением (для undo)
            self._data = ref.serialize_data()
            self._entity.remove_component_ref(ref)

    def undo(self) -> None:
        # Проверяем, что компонента нет
        if self._entity.has_tc_component(self._type_name):
            return

        # Создаём компонент заново
        ref = self._entity.add_component_by_name(self._type_name)

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
        self._parent_transform = parent_transform

    @property
    def entity(self) -> Entity:
        return self._entity

    @property
    def parent_entity(self) -> Entity | None:
        if self._parent_transform is None:
            return None
        return self._parent_transform.entity if self._parent_transform is not None else None

    def do(self) -> None:
        if self._parent_transform is not None:
            self._entity.transform.set_parent(self._parent_transform)

        # scene.add() will migrate if needed, or just register components if already in pool
        self._entity = self._scene.add(self._entity)

    def undo(self) -> None:
        self._scene.remove(self._entity)
        

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
        self._parent_transform = entity.transform.parent

    @property
    def entity(self) -> Entity:
        return self._entity

    @property
    def parent_entity(self) -> Entity | None:
        if self._parent_transform is None:
            return None
        return self._parent_transform.entity if self._parent_transform is not None else None

    def do(self) -> None:
        self._scene.remove(self._entity)

    def undo(self) -> None:
        if self._parent_transform is not None:
            self._entity.transform.set_parent(self._parent_transform)

        self._scene.add(self._entity)


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
        self._entity = entity
        self._old_parent = old_parent
        self._new_parent = new_parent
        # Сохраняем local pose для undo
        self._old_local_pose = _clone_pose(entity.transform.local_pose())

    @property
    def entity(self) -> Entity:
        return self._entity

    def do(self) -> None:
        # Сохраняем global pose до смены родителя
        global_pose = self._entity.transform.global_pose()
        # Меняем родителя
        self._entity.transform.set_parent(self._new_parent)
        # Восстанавливаем global pose (пересчитывает local pose)
        self._entity.transform.relocate_global(global_pose)

    def undo(self) -> None:
        # Возвращаем родителя и восстанавливаем оригинальный local pose
        self._entity.transform.set_parent(self._old_parent)
        self._entity.transform.relocate(self._old_local_pose)


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
        self._old_name = old_name
        self._new_name = new_name

    @property
    def entity(self) -> Entity:
        return self._entity

    def do(self) -> None:
        self._entity.name = self._new_name

    def undo(self) -> None:
        self._entity.name = self._old_name

    def merge_with(self, other: UndoCommand) -> bool:
        """
        Склейка последовательных переименований одной и той же сущности.
        """
        if not isinstance(other, RenameEntityCommand):
            return False
        if other._entity is not self._entity:
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
        self._source_entity = source_entity
        self._parent_transform = source_entity.transform.parent
        self._copy: Entity | None = None

        # Serialize source for do/redo
        self._serialized_data = source_entity.serialize()
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
            self._serialized_data, context=None, scene=self._scene
        )
        self._copy.name = f"{self._source_entity.name}_copy"

        # Set parent
        if self._parent_transform is not None:
            self._copy.transform.set_parent(self._parent_transform)

    def undo(self) -> None:
        if self._copy is not None:
            self._scene.remove(self._copy)
            self._copy = None
