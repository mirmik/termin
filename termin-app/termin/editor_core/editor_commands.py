from __future__ import annotations

import copy
import logging
from typing import Any

import numpy as np

from termin.editor_core.undo_stack import UndoCommand
from termin.geombase import GeneralPose3
from termin.kinematic.general_transform import GeneralTransform3
from termin.scene import Entity, Component
from termin.scene import TcComponentRef
from termin.inspect import InspectField
from termin.render import scene_render_state


_logger = logging.getLogger(__name__)


_SCENE_RENDER_STATE_PROPERTIES = {
    "background_color",
    "ambient_color",
    "ambient_intensity",
    "skybox_color",
    "skybox_top_color",
    "skybox_bottom_color",
    "skybox_type",
}


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
    делается copy(); для контейнеров делается deepcopy, чтобы undo-команды
    не держали изменяемые ссылки на значения инспектора.
    """
    if isinstance(value, np.ndarray):
        return value.copy()
    if isinstance(value, (list, tuple, dict)):
        return copy.deepcopy(value)
    return value


def _set_scene_render_state_property(scene, property_name: str, value: Any) -> None:
    rs = scene_render_state(scene)
    if property_name == "background_color":
        rs.background_color = _coerce_scene_vector_value(rs.background_color, value)
        return
    if property_name == "ambient_color":
        rs.ambient_color = _coerce_scene_vector_value(rs.ambient_color, value)
        return
    if property_name == "ambient_intensity":
        rs.ambient_intensity = float(value)
        return
    if property_name == "skybox_color":
        rs.skybox_color = _coerce_scene_vector_value(rs.skybox_color, value)
        return
    if property_name == "skybox_top_color":
        rs.skybox_top_color = _coerce_scene_vector_value(rs.skybox_top_color, value)
        return
    if property_name == "skybox_bottom_color":
        rs.skybox_bottom_color = _coerce_scene_vector_value(rs.skybox_bottom_color, value)
        return
    if property_name == "skybox_type":
        rs.skybox_type = str(value)
        return
    _logger.error("Unsupported scene render state property: %s", property_name)
    raise RuntimeError(f"Unsupported scene render state property: {property_name}")


def _coerce_scene_vector_value(current_value: Any, value: Any) -> Any:
    if isinstance(value, np.ndarray):
        components = value.reshape(-1).tolist()
    elif isinstance(value, (list, tuple)):
        components = list(value)
    else:
        components = [value[i] for i in range(len(value))]

    target_len = len(current_value)
    if target_len == 4 and len(components) == 3:
        components.append(1.0)
    if len(components) < target_len:
        _logger.error(
            "Scene vector value has %d components, expected %d",
            len(components),
            target_len,
        )
        raise RuntimeError("Scene vector value has too few components")
    return current_value.__class__(*[float(v) for v in components[:target_len]])


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
        if self._ref.type_name != self._type_name:
            actual_type = self._ref.type_name
            _logger.error(
                "Component registry created '%s' while '%s' was requested",
                actual_type,
                self._type_name,
            )
            entity.remove_component_ref(self._ref)
            self._ref = None
            raise RuntimeError(
                f"component registry returned '{actual_type}' for '{self._type_name}'"
            )

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


class ComponentDisplayNameEditCommand(UndoCommand):
    """Команда изменения display_name у tc component."""

    def __init__(
        self,
        component: TcComponentRef,
        old_name: str,
        new_name: str,
        text: str = "Rename component",
    ) -> None:
        super().__init__(text)
        entity = _component_entity(component)
        self._scene = entity.scene if entity is not None else None
        self._entity_uuid = _entity_uuid(entity)
        self._component_type_name = _component_type_name(component)
        self._component = component
        self._old_name = old_name
        self._new_name = new_name

    def _current_component(self) -> TcComponentRef:
        if self._scene is not None:
            self._component = _resolve_command_component(
                self._scene,
                self._entity_uuid,
                self._component_type_name,
                self.text,
            )
            return self._component
        if self._component.valid:
            return self._component
        _logger.error(
            "ComponentDisplayNameEditCommand has no live component entity=%s component=%s",
            self._entity_uuid,
            self._component_type_name,
        )
        raise RuntimeError("ComponentDisplayNameEditCommand has no live component")

    def do(self) -> None:
        self._current_component().set_field("display_name", self._new_name)

    def undo(self) -> None:
        self._current_component().set_field("display_name", self._old_name)


class EntityPropertyEditCommand(UndoCommand):
    """Команда изменения простых свойств entity."""

    def __init__(
        self,
        entity: Entity,
        property_name: str,
        old_value: Any,
        new_value: Any,
        text: str | None = None,
    ) -> None:
        if text is None:
            text = f"Edit entity {property_name}"
        super().__init__(text)
        self._entity = entity
        self._scene = entity.scene
        self._entity_uuid = _entity_uuid(entity)
        self._property_name = property_name
        self._old_value = old_value
        self._new_value = new_value

    def _current_entity(self) -> Entity:
        if _entity_is_valid(self._entity):
            return self._entity
        self._entity = _resolve_command_entity(self._scene, self._entity_uuid, self.text)
        return self._entity

    def _apply(self, value: Any) -> None:
        entity = self._current_entity()
        if self._property_name == "name":
            entity.name = str(value)
            return
        if self._property_name == "layer":
            entity.layer = int(value)
            return
        if self._property_name == "visible":
            entity.visible = bool(value)
            return
        _logger.error("Unsupported entity property for undo command: %s", self._property_name)
        raise RuntimeError(f"Unsupported entity property: {self._property_name}")

    def do(self) -> None:
        self._apply(self._new_value)

    def undo(self) -> None:
        self._apply(self._old_value)

    def merge_with(self, other: UndoCommand) -> bool:
        if not isinstance(other, EntityPropertyEditCommand):
            return False
        if other._entity_uuid != self._entity_uuid:
            return False
        if other._property_name != self._property_name:
            return False
        self._new_value = other._new_value
        return True


class RecursiveLayerChangeCommand(UndoCommand):
    """Команда изменения слоя у набора entity."""

    def __init__(
        self,
        entities_and_old_layers: list[tuple[Entity, int]],
        new_layer: int,
        text: str = "Apply layer to descendants",
    ) -> None:
        super().__init__(text)
        self._items = [
            (entity, entity.scene, _entity_uuid(entity), int(old_layer))
            for entity, old_layer in entities_and_old_layers
        ]
        self._new_layer = int(new_layer)

    def _apply(self, use_new_layer: bool) -> None:
        for entity, scene, entity_uuid, old_layer in self._items:
            current = entity
            if not _entity_is_valid(current):
                current = _resolve_command_entity(scene, entity_uuid, self.text)
            current.layer = self._new_layer if use_new_layer else old_layer

    def do(self) -> None:
        self._apply(True)

    def undo(self) -> None:
        self._apply(False)


class AddSoAComponentCommand(UndoCommand):
    """Команда добавления SoA component по имени типа."""

    def __init__(
        self,
        entity: Entity,
        soa_name: str,
        text: str = "Add SoA component",
    ) -> None:
        super().__init__(text)
        self._entity = entity
        self._scene = entity.scene
        self._entity_uuid = _entity_uuid(entity)
        self._soa_name = soa_name

    def _current_entity(self) -> Entity:
        if _entity_is_valid(self._entity):
            return self._entity
        self._entity = _resolve_command_entity(self._scene, self._entity_uuid, self.text)
        return self._entity

    def do(self) -> None:
        entity = self._current_entity()
        if self._soa_name in entity.soa_component_names:
            return
        entity.add_soa_by_name(self._soa_name)

    def undo(self) -> None:
        entity = self._current_entity()
        if self._soa_name not in entity.soa_component_names:
            return
        entity.remove_soa_by_name(self._soa_name)


class RemoveSoAComponentCommand(UndoCommand):
    """Команда удаления SoA component по имени типа."""

    def __init__(
        self,
        entity: Entity,
        soa_name: str,
        text: str = "Remove SoA component",
    ) -> None:
        super().__init__(text)
        self._entity = entity
        self._scene = entity.scene
        self._entity_uuid = _entity_uuid(entity)
        self._soa_name = soa_name

    def _current_entity(self) -> Entity:
        if _entity_is_valid(self._entity):
            return self._entity
        self._entity = _resolve_command_entity(self._scene, self._entity_uuid, self.text)
        return self._entity

    def do(self) -> None:
        entity = self._current_entity()
        if self._soa_name not in entity.soa_component_names:
            return
        entity.remove_soa_by_name(self._soa_name)

    def undo(self) -> None:
        entity = self._current_entity()
        if self._soa_name in entity.soa_component_names:
            return
        entity.add_soa_by_name(self._soa_name)


class ScenePropertyEditCommand(UndoCommand):
    """Команда изменения поля scene render state."""

    def __init__(
        self,
        scene,
        property_name: str,
        old_value: Any,
        new_value: Any,
        text: str | None = None,
    ) -> None:
        if property_name not in _SCENE_RENDER_STATE_PROPERTIES:
            _logger.error("Unsupported scene render state property: %s", property_name)
            raise RuntimeError(f"Unsupported scene render state property: {property_name}")
        if text is None:
            text = f"Edit scene {property_name}"
        super().__init__(text)
        self._scene = scene
        self._property_name = property_name
        self._old_value = _clone_value(old_value)
        self._new_value = _clone_value(new_value)

    def do(self) -> None:
        _set_scene_render_state_property(self._scene, self._property_name, self._new_value)

    def undo(self) -> None:
        _set_scene_render_state_property(self._scene, self._property_name, self._old_value)

    def merge_with(self, other: UndoCommand) -> bool:
        if not isinstance(other, ScenePropertyEditCommand):
            return False
        if other._scene is not self._scene:
            return False
        if other._property_name != self._property_name:
            return False
        self._new_value = _clone_value(other._new_value)
        return True


class SkyboxTypeEditCommand(ScenePropertyEditCommand):
    """Команда изменения skybox type."""

    def __init__(
        self,
        scene,
        old_type: str,
        new_type: str,
        text: str = "Edit skybox type",
    ) -> None:
        super().__init__(scene, "skybox_type", old_type, new_type, text)


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
        new_sibling_index: int | None = None,
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
        self._old_sibling_index = int(entity.sibling_index)
        self._new_sibling_index = new_sibling_index
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
        if self._new_sibling_index is not None:
            entity.sibling_index = self._new_sibling_index
        # Восстанавливаем global pose (пересчитывает local pose)
        entity.transform.relocate_global(global_pose)

    def undo(self) -> None:
        entity = self._current_entity()
        # Возвращаем родителя и восстанавливаем оригинальный local pose
        entity.transform.set_parent(_resolve_parent_transform(self._scene, self._old_parent_uuid))
        entity.sibling_index = self._old_sibling_index
        entity.transform.relocate(self._old_local_pose)


__all__ = [
    "TransformEditCommand",
    "ComponentFieldEditCommand",
    "AddComponentCommand",
    "RemoveComponentCommand",
    "ComponentDisplayNameEditCommand",
    "EntityPropertyEditCommand",
    "RecursiveLayerChangeCommand",
    "AddSoAComponentCommand",
    "RemoveSoAComponentCommand",
    "ScenePropertyEditCommand",
    "SkyboxTypeEditCommand",
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

        source_data = source_entity.serialize_hierarchy()
        clone_payload, uuid_remap = Entity.make_clone_payload(source_data, "_copy")
        self._serialized_data = Entity.remap_entity_refs(clone_payload, uuid_remap)

    @property
    def entity(self) -> Entity | None:
        """The duplicated entity (available after do())."""
        return self._copy

    def do(self) -> None:
        parent = _resolve_scene_entity(self._scene, self._parent_uuid)
        self._copy = Entity.deserialize_hierarchy(
            copy.deepcopy(self._serialized_data),
            self._scene,
            parent,
        )
        if self._copy is None or not self._copy.valid():
            _logger.error("Failed to duplicate entity '%s' while applying undo command '%s'",
                          self._source_name, self.text)
            raise RuntimeError(f"Failed to duplicate entity '{self._source_name}'")

    def undo(self) -> None:
        if self._copy is not None:
            _remove_entity_tree(self._scene, self._copy)
            self._copy = None
