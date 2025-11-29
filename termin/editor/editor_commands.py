from __future__ import annotations

from typing import Any

import numpy as np

from termin.editor.undo_stack import UndoCommand
from termin.geombase.pose3 import Pose3
from termin.kinematic.transform import Transform3
from termin.visualization.core.entity import Entity, Component
from termin.editor.inspect_field import InspectField


def _clone_pose(pose: Pose3) -> Pose3:
    """
    Создаёт независимую копию позы.

    Массивы угла и смещения копируются, чтобы последующие
    изменения позы не портили снимок для undo/redo.
    """
    return Pose3(ang=pose.ang.copy(), lin=pose.lin.copy())


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

    Ожидается, что transform принадлежит entity
    (transform.entity is entity), а масштаб хранится в виде
    вектора длины 3 в Entity.scale.
    """

    def __init__(
        self,
        transform: Transform3,
        old_pose: Pose3,
        old_scale: np.ndarray,
        new_pose: Pose3,
        new_scale: np.ndarray,
        text: str = "Transform change",
    ) -> None:
        super().__init__(text)
        self._transform = transform
        self._entity = transform.entity
        self._old_pose = _clone_pose(old_pose)
        self._old_scale = np.asarray(old_scale, dtype=float).copy()
        self._new_pose = _clone_pose(new_pose)
        self._new_scale = np.asarray(new_scale, dtype=float).copy()

    def do(self) -> None:
        if self._entity is not None:
            self._entity.scale = self._new_scale
        self._transform.relocate(self._new_pose)

    def undo(self) -> None:
        if self._entity is not None:
            self._entity.scale = self._old_scale
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
        self._new_scale = np.asarray(other._new_scale, dtype=float).copy()
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


__all__ = [
    "TransformEditCommand",
    "ComponentFieldEditCommand",
    "AddComponentCommand",
    "RemoveComponentCommand",
]
