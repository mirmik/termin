"""Scene entity storing components (Unity-like architecture)."""

from __future__ import annotations

from typing import List, Optional, Type, TypeVar, TYPE_CHECKING

import numpy as np

from termin.geombase import Pose3
from termin.geombase import GeneralPose3
from termin.kinematic.general_transform import GeneralTransform3
from termin.visualization.core.identifiable import Identifiable
from termin.visualization.core.resources import ResourceManager
from termin.visualization.core.component import Component, InputComponent

if TYPE_CHECKING:  # pragma: no cover
    from termin.visualization.core.scene import Scene

from termin.visualization.core.serialization import COMPONENT_REGISTRY


C = TypeVar("C", bound=Component)


class Entity(Identifiable):
    """Container of components with transform data."""

    def __init__(
        self,
        pose: Pose3 | GeneralPose3 = None,
        name: str = "entity",
        priority: int = 0,
        pickable: bool = True,
        selectable: bool = True,
        serializable: bool = True,
        layer: int = 0,
        flags: int = 0,
        uuid: str | None = None,
    ):
        super().__init__(uuid=uuid)
        # Convert pose to GeneralPose3
        if pose is None:
            general_pose = GeneralPose3()
        elif isinstance(pose, GeneralPose3):
            general_pose = pose.copy()
        else:
            # Pose3 -> GeneralPose3
            general_pose = GeneralPose3(
                ang=pose.ang.copy(),
                lin=pose.lin.copy(),
            )

        self.transform = GeneralTransform3(general_pose)
        self.transform.entity = self
        self.visible = True
        self.active = True
        self.name = name
        self.priority = priority  # rendering priority, lower values drawn first
        self._components: List[Component] = []
        self.scene: Optional["Scene"] = None
        self.pickable = pickable
        self.selectable = selectable
        self.serializable = serializable  # False для редакторных сущностей (гизмо и т.д.)
        self._pick_id: int | None = None
        self.layer: int = max(0, min(63, layer))  # 0-63
        self.flags: int = flags & 0xFFFFFFFFFFFFFFFF  # 64-bit mask

        # Register in global registry for EntityHandle resolution
        from termin.visualization.core.entity_registry import EntityRegistry
        EntityRegistry.instance().register(self)

    def __post_init__(self):
        self.scene: Optional["Scene"] = None
        self._components: List[Component] = []

    def model_matrix(self) -> np.ndarray:
        """Construct homogeneous model matrix with scale baked in."""
        return self.transform.global_pose().as_matrix()

    def inverse_model_matrix(self) -> np.ndarray:
        """Construct inverse model matrix (cached in GeneralPose3)."""
        return self.transform.global_pose().inverse_matrix()

    def set_visible(self, flag: bool):
        self.visible = flag
        for child in self.transform.children:
            if child.entity is not None:
                child.entity.set_visible(flag)


    def is_pickable(self) -> bool:
        return self.pickable and self.visible and self.active

    @property
    def pick_id(self) -> int:
        """Уникальный идентификатор сущности для pick-проходов (hash от uuid)."""
        if self._pick_id is None:
            # Stable hash from uuid (take lower 31 bits of uuid int value)
            uuid_int = int(self.uuid.replace("-", ""), 16)
            h = uuid_int & 0x7FFFFFFF  # 31-bit positive int
            if h == 0:
                h = 1  # 0 means "nothing hit"
            self._pick_id = h
            from termin.visualization.core.entity_registry import EntityRegistry
            EntityRegistry.instance().register_pick_id(h, self)
        return self._pick_id

    @classmethod
    def lookup_by_pick_id(cls, pid: int) -> "Entity | None":
        from termin.visualization.core.entity_registry import EntityRegistry
        return EntityRegistry.instance().get_by_pick_id(pid)

    def add_component(self, component: Component) -> Component:
        component.entity = self
        self._components.append(component)
        if self.scene is not None:
            self.scene.register_component(component)
            component.on_added(self.scene)
        return component

    def remove_component(self, component: Component):
        if component not in self._components:
            return
        self._components.remove(component)
        if self.scene is not None:
            self.scene.unregister_component(component)
        component.on_removed()
        component.entity = None

    def get_component(self, component_type: Type[C]) -> Optional[C]:
        for comp in self._components:
            if isinstance(comp, component_type):
                return comp
        return None

    def find_component(self, component_type: Type[C]) -> C:
        comp = self.get_component(component_type)
        if comp is None:
            raise ValueError(f"Component of type {component_type} not found in entity {self.name}")
        return comp

    @property
    def components(self) -> List[Component]:
        return list(self._components)

    def update(self, dt: float):
        if not self.active:
            return
        for component in self._components:
            if component.enabled:
                component.update(dt)

    def on_added(self, scene: "Scene"):
        self.scene = scene
        for component in self._components:
            scene.register_component(component)
            component.on_added(scene)

    def on_removed(self):
        for component in self._components:
            if self.scene is not None:
                self.scene.unregister_component(component)
            component.on_removed()
            component.entity = None
        self.scene = None

        # Очищаем pick_id из глобального реестра
        if self._pick_id is not None:
            from termin.visualization.core.entity_registry import EntityRegistry
            EntityRegistry.instance().unregister_pick_id(self._pick_id)
            self._pick_id = None

    def serialize(self):
        if not self.serializable:
            return None

        # Check if this is a prefab instance (has PrefabInstanceMarker)
        from termin.visualization.core.prefab_instance_marker import PrefabInstanceMarker
        marker = self.get_component(PrefabInstanceMarker)

        if marker is not None:
            # Compact prefab instance format
            return self._serialize_as_prefab_instance(marker)

        # Full entity serialization
        return self._serialize_full()

    def _serialize_as_prefab_instance(self, marker: "PrefabInstanceMarker") -> dict:
        """Serialize as prefab instance (compact format with overrides only)."""
        from termin.visualization.core.prefab_instance_marker import PrefabInstanceMarker

        pose = self.transform.local_pose()
        data = {
            "prefab_uuid": marker.prefab_uuid,
            "instance_uuid": self.uuid,
            "pose": {
                "position": list(pose.lin),
                "rotation": list(pose.ang),
            },
            "scale": list(pose.scale),
            "overrides": marker.overrides.copy(),
        }

        # Store name if different from default (will be checked on load)
        data["name"] = self.name

        # Children that were added to the instance (not from prefab)
        if marker.added_children:
            data["added_children"] = []
            for child_uuid in marker.added_children:
                # Find child and serialize it fully
                for child_transform in self.transform.children:
                    child_ent = child_transform.entity
                    if child_ent is not None and child_ent.uuid == child_uuid:
                        child_data = child_ent._serialize_full()
                        if child_data is not None:
                            data["added_children"].append(child_data)
                        break

        # UUIDs of children removed from instance
        if marker.removed_children:
            data["removed_children"] = list(marker.removed_children)

        return data

    def _serialize_full(self) -> dict:
        """Full entity serialization (non-prefab or prefab source)."""
        pose = self.transform.local_pose()
        data = {
            "uuid": self.uuid,
            "name": self.name,
            "priority": self.priority,
            "scale": list(pose.scale),
            "visible": self.visible,
            "active": self.active,
            "pickable": self.pickable,
            "selectable": self.selectable,
            "layer": self.layer,
            "flags": self.flags,
            "pose": {
                "position": list(pose.lin),
                "rotation": list(pose.ang),
            },
            "components": [
                comp.serialize()
                for comp in self.components
                if comp.serialize() is not None
            ],
            "children": [],
        }

        # Сериализуем дочерние Entity через Transform.children (только serializable)
        for child_transform in self.transform.children:
            child_ent = child_transform.entity
            if child_ent is not None and child_ent.serializable:
                child_data = child_ent.serialize()
                if child_data is not None:
                    data["children"].append(child_data)

        return data


    @classmethod
    def deserialize(cls, data, context=None):
        # Check if this is a prefab instance (compact format)
        if "prefab_uuid" in data:
            return cls._deserialize_prefab_instance(data, context)

        # Full entity deserialization
        return cls._deserialize_full(data, context)

    @classmethod
    def _deserialize_prefab_instance(cls, data: dict, context=None) -> "Entity":
        """Deserialize a prefab instance from compact format."""
        import numpy as np
        from termin.visualization.core.prefab_instance_marker import PrefabInstanceMarker

        prefab_uuid = data["prefab_uuid"]
        rm = ResourceManager.instance()

        # Get the prefab asset
        prefab = rm.get_prefab_by_uuid(prefab_uuid)
        if prefab is None:
            print(f"[Entity] Prefab not found: {prefab_uuid}, falling back to empty entity")
            # Create empty entity as fallback
            return cls(name=data.get("name", "missing_prefab"))

        # Instantiate the prefab (creates new entity hierarchy with marker)
        position = tuple(data["pose"]["position"]) if "pose" in data else None
        entity = prefab.instantiate(position=position, name=data.get("name"))

        # Override the instance UUID to restore identity
        if "instance_uuid" in data:
            entity._uuid = data["instance_uuid"]
            # Re-register with new UUID
            from termin.visualization.core.entity_registry import EntityRegistry
            EntityRegistry.instance().register(entity)

        # Apply pose (rotation might be different)
        if "pose" in data:
            pose = entity.transform.local_pose()
            pose.lin[...] = data["pose"]["position"]
            pose.ang[...] = data["pose"]["rotation"]
            if "scale" in data:
                pose.scale[...] = data["scale"]
            entity.transform.set_local_pose(pose)

        # Get the marker and restore overrides
        marker = entity.get_component(PrefabInstanceMarker)
        if marker is not None:
            # Restore overrides from saved data
            overrides = data.get("overrides", {})
            for path, value in overrides.items():
                marker.set_override(path, value)

            # Apply overrides to entity
            from termin.visualization.core.property_path import PropertyPath
            for path, value in overrides.items():
                try:
                    # Deserialize value if needed
                    deserialized = prefab._deserialize_property_value(path, value)
                    PropertyPath.set(entity, path, deserialized)
                except Exception as e:
                    print(f"[Entity] Cannot apply override {path}: {e}")

            # Handle removed children
            removed_children = data.get("removed_children", [])
            for child_uuid in removed_children:
                marker.mark_child_removed(child_uuid)
                # Find and remove the child
                for child_transform in list(entity.transform.children):
                    child_ent = child_transform.entity
                    if child_ent is not None and child_ent.uuid == child_uuid:
                        entity.transform.remove_child(child_transform)
                        break

        # Handle added children
        added_children = data.get("added_children", [])
        for child_data in added_children:
            child_ent = cls.deserialize(child_data, context)
            entity.transform.add_child(child_ent.transform)
            if marker is not None:
                marker.mark_child_added(child_ent.uuid)

        return entity

    @classmethod
    def _deserialize_full(cls, data: dict, context=None) -> "Entity":
        """Full entity deserialization (non-prefab)."""
        import numpy as np

        ent = cls(
            pose=GeneralPose3(
                lin=np.array(data["pose"]["position"]),
                ang=np.array(data["pose"]["rotation"]),
                scale=np.array(data.get("scale", [1.0, 1.0, 1.0])),
            ),
            name=data["name"],
            priority=data.get("priority", 0),
            pickable=data.get("pickable", True),
            selectable=data.get("selectable", True),
            layer=data.get("layer", 0),
            flags=data.get("flags", 0),
            uuid=data.get("uuid"),
        )

        # Восстанавливаем дополнительные поля
        ent.visible = data.get("visible", True)
        ent.active = data.get("active", True)

        # Компоненты
        rm = ResourceManager.instance()
        for c in data.get("components", []):
            comp_type = c.get("type")
            if comp_type is None:
                continue
            # Пробуем сначала COMPONENT_REGISTRY, потом ResourceManager
            comp_cls = COMPONENT_REGISTRY.get(comp_type)
            if comp_cls is None:
                comp_cls = rm.get_component(comp_type)
            if comp_cls is None:
                # Неизвестный компонент - пропускаем
                continue
            comp = comp_cls.deserialize(c.get("data", {}), context)
            ent.add_component(comp)

        # Дочерние Entity
        for child_data in data.get("children", []):
            child_ent = cls.deserialize(child_data, context)
            ent.transform.add_child(child_ent.transform)

        return ent
