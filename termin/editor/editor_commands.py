from __future__ import annotations

from typing import Any

import numpy as np

from termin.editor.undo_stack import UndoCommand
from termin.geombase.general_pose3 import GeneralPose3
from termin.kinematic.general_transform import GeneralTransform3
from termin.visualization.core.entity import Entity, Component
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

    В do() компонент добавляется, в undo() — удаляется.
    Позиция компонента в списке может немного "плавать", если
    между командами сильно менялась структура, но базовый сценарий
    (откат сразу после добавления) поддерживается корректно.
    """

    def __init__(
        self,
        entity: Entity,
        component: Component,
        text: str = "Add component",
    ) -> None:
        super().__init__(text)
        self._entity = entity
        self._component = component

    def do(self) -> None:
        # Entity.components возвращает копию списка, поэтому
        # проверка "компонент уже добавлен" безопасна.
        if self._component not in self._entity.components:
            self._entity.add_component(self._component)

    def undo(self) -> None:
        self._entity.remove_component(self._component)


class RemoveComponentCommand(UndoCommand):
    """
    Удаление компонента из сущности.

    В do() компонент удаляется, в undo() — добавляется обратно.
    """

    def __init__(
        self,
        entity: Entity,
        component: Component,
        text: str = "Remove component",
    ) -> None:
        super().__init__(text)
        self._entity = entity
        self._component = component

    def do(self) -> None:
        self._entity.remove_component(self._component)

    def undo(self) -> None:
        # Если кто-то уже вернул компонент руками — лишний раз
        # не добавляем.
        if self._component not in self._entity.components:
            self._entity.add_component(self._component)


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

        self._scene.add(self._entity)

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

    @property
    def entity(self) -> Entity:
        return self._entity

    def do(self) -> None:
        self._entity.transform.set_parent(self._new_parent)

    def undo(self) -> None:
        self._entity.transform.set_parent(self._old_parent)


__all__ = [
    "TransformEditCommand",
    "ComponentFieldEditCommand",
    "AddComponentCommand",
    "RemoveComponentCommand",
    "AddEntityCommand",
    "DeleteEntityCommand",
    "ReparentEntityCommand",
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
