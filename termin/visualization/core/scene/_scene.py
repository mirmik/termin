"""Simple scene graph storing entities and global parameters."""

from __future__ import annotations

from typing import Callable, List, Sequence, TYPE_CHECKING

import numpy as np

from termin.visualization.core.component import Component, InputComponent
from termin.visualization.core.entity import Entity
from termin._native.scene import TcScene
from termin.lighting import Light
from termin.visualization.render.components.light_component import LightComponent
from termin.geombase import Ray3
from termin.colliders.raycast_hit import RaycastHit
from termin.collision._collision_native import CollisionWorld
from termin.core import Event

from .skybox import SkyboxManager
from .lighting import LightingManager


if TYPE_CHECKING:  # pragma: no cover
    from termin.visualization.core.mesh_handle import MeshHandle
    from termin.visualization.core.material import Material


def _vec3_to_np(v) -> np.ndarray:
    return np.array([v.x, v.y, v.z])


def is_overrides_method(obj, method_name, base_class):
    return getattr(obj.__class__, method_name) is not getattr(base_class, method_name)


class Scene:
    """Container for renderable entities and lighting data."""

    def __init__(
        self,
        background_color: Sequence[float] = (0.05, 0.05, 0.08, 1.0),
        uuid: str | None = None,
    ):
        # C core scene for optimized entity/component management
        self._tc_scene = TcScene()

        # Identifiable fields
        self.uuid = uuid or ""
        self.runtime_id = 0

        # Python-side entity list (for Python iteration)
        self._entities: List[Entity] = []
        # Background color with alpha
        self._background_color = np.array(background_color, dtype=np.float32)
        self._input_components: List[InputComponent] = []
        self.colliders = []
        self._collision_world = CollisionWorld()

        # Skybox manager
        self._skybox = SkyboxManager()

        # Lighting manager
        self._lighting = LightingManager()

        # Layer and flag names (index -> name)
        self.layer_names: dict[int, str] = {}  # 0-63
        self.flag_names: dict[int, str] = {}   # 0-63 (bit index)

        # Entity lifecycle events
        self._on_entity_added: Event[Entity] = Event()
        self._on_entity_removed: Event[Entity] = Event()

    # --- Background color (with alpha, C++ only has RGB) ---

    @property
    def background_color(self) -> np.ndarray:
        return self._background_color

    @background_color.setter
    def background_color(self, value):
        self._background_color = np.asarray(value, dtype=np.float32)

    # --- Skybox delegation (backward compatibility) ---

    @property
    def skybox_type(self) -> str:
        return self._skybox.skybox_type

    @skybox_type.setter
    def skybox_type(self, value: str):
        self._skybox.skybox_type = value

    @property
    def skybox_color(self) -> np.ndarray:
        return self._skybox.skybox_color

    @skybox_color.setter
    def skybox_color(self, value):
        self._skybox.skybox_color = np.asarray(value, dtype=np.float32)

    @property
    def skybox_top_color(self) -> np.ndarray:
        return self._skybox.skybox_top_color

    @skybox_top_color.setter
    def skybox_top_color(self, value):
        self._skybox.skybox_top_color = np.asarray(value, dtype=np.float32)

    @property
    def skybox_bottom_color(self) -> np.ndarray:
        return self._skybox.skybox_bottom_color

    @skybox_bottom_color.setter
    def skybox_bottom_color(self, value):
        self._skybox.skybox_bottom_color = np.asarray(value, dtype=np.float32)

    def skybox_mesh(self) -> "MeshHandle":
        """Get skybox cube mesh."""
        return self._skybox.mesh

    def skybox_material(self) -> "Material | None":
        """Get skybox material based on current skybox_type."""
        return self._skybox.material

    def set_skybox_type(self, skybox_type: str) -> None:
        """Set skybox type and reset material if type changed."""
        self._skybox.set_type(skybox_type)

    # --- Lighting delegation (backward compatibility) ---

    @property
    def lights(self) -> List[Light]:
        return self._lighting.lights

    @lights.setter
    def lights(self, value: List[Light]):
        self._lighting.lights = value

    @property
    def light_direction(self) -> np.ndarray:
        return self._lighting.light_direction

    @light_direction.setter
    def light_direction(self, value):
        self._lighting.light_direction = np.asarray(value, dtype=np.float32)

    @property
    def light_color(self) -> np.ndarray:
        return self._lighting.light_color

    @light_color.setter
    def light_color(self, value):
        self._lighting.light_color = np.asarray(value, dtype=np.float32)

    @property
    def ambient_color(self) -> np.ndarray:
        return self._lighting.ambient_color

    @ambient_color.setter
    def ambient_color(self, value):
        self._lighting.ambient_color = np.asarray(value, dtype=np.float32)

    @property
    def ambient_intensity(self) -> float:
        return self._lighting.ambient_intensity

    @ambient_intensity.setter
    def ambient_intensity(self, value: float):
        self._lighting.ambient_intensity = value

    @property
    def light_components(self) -> List[LightComponent]:
        return self._lighting.light_components

    @property
    def shadow_settings(self):
        """Shadow rendering settings."""
        from .lighting import ShadowSettings
        return self._lighting.shadow_settings

    def build_lights(self) -> List[Light]:
        """Build world-space light parameters from all light components."""
        return self._lighting.build_lights()

    # --- Collision World ---

    @property
    def collision_world(self) -> CollisionWorld:
        """Get the collision world for physics and raycasting."""
        return self._collision_world

    # --- Raycast ---

    def raycast(self, ray: Ray3):
        """
        Returns first intersection with any ColliderComponent
        where distance == 0 (exact hit).
        """
        best_hit = None
        best_ray_dist = float("inf")
        origin = _vec3_to_np(ray.origin)

        for comp in self.colliders:
            attached = comp.attached
            if attached is None:
                continue

            hit = attached.closest_to_ray(ray)
            if hit.distance != 0.0:
                continue

            p_ray = _vec3_to_np(hit.point_on_ray)
            d_ray = np.linalg.norm(p_ray - origin)

            if d_ray < best_ray_dist:
                best_ray_dist = d_ray
                best_hit = RaycastHit(
                    comp.entity, comp, p_ray, _vec3_to_np(hit.point_on_collider), 0.0
                )

        return best_hit

    def closest_to_ray(self, ray: Ray3):
        """
        Returns closest object to ray (minimum distance).
        Does not require intersection.
        """
        best_hit = None
        best_dist = float("inf")

        for comp in self.colliders:
            attached = comp.attached
            if attached is None:
                continue

            hit = attached.closest_to_ray(ray)
            if hit.distance < best_dist:
                best_dist = hit.distance
                best_hit = RaycastHit(
                    comp.entity, comp,
                    _vec3_to_np(hit.point_on_ray),
                    _vec3_to_np(hit.point_on_collider),
                    hit.distance
                )

        return best_hit

    # --- Layer and flag names ---

    def get_layer_name(self, index: int) -> str:
        """Get layer name by index, or default 'Layer N'."""
        return self.layer_names.get(index, f"Layer {index}")

    def get_flag_name(self, index: int) -> str:
        """Get flag name by bit index, or default 'Flag N'."""
        return self.flag_names.get(index, f"Flag {index}")

    def set_layer_name(self, index: int, name: str):
        """Set layer name. Empty name removes the entry."""
        if name:
            self.layer_names[index] = name
        else:
            self.layer_names.pop(index, None)

    def set_flag_name(self, index: int, name: str):
        """Set flag name. Empty name removes the entry."""
        if name:
            self.flag_names[index] = name
        else:
            self.flag_names.pop(index, None)

    # --- Entity management ---

    @property
    def entities(self) -> List[Entity]:
        """Get all entities in the scene."""
        return self._entities

    def add_non_recurse(self, entity: Entity) -> Entity:
        """Add entity to the scene, keeping the entities list sorted by priority."""
        # Insert sorted by priority (Python-side list)
        idx = 0
        for i, e in enumerate(self._entities):
            if e.priority > entity.priority:
                idx = i
                break
            idx = i + 1
        self._entities.insert(idx, entity)

        # Add to C core scene
        self._tc_scene.add_entity(entity)

        # Python-specific: set scene reference and emit Event
        entity.on_added(self)
        self._on_entity_added.emit(entity)
        return entity

    def add(self, entity: Entity) -> Entity:
        """Add entity to the scene, including all its children."""
        self.add_non_recurse(entity)
        for child in entity.children():
            self.add(child)
        return entity

    def remove(self, entity: Entity):
        # Remove from Python list
        if entity in self._entities:
            self._entities.remove(entity)

        # Remove from C core scene
        self._tc_scene.remove_entity(entity)

        # Python-specific: emit Event and cleanup
        self._on_entity_removed.emit(entity)
        entity.on_removed()

    @property
    def on_entity_added(self) -> Event[Entity]:
        return self._on_entity_added

    @on_entity_added.setter
    def on_entity_added(self, value: Event[Entity]):
        pass  # __iadd__ modifies in place, setter is no-op

    @property
    def on_entity_removed(self) -> Event[Entity]:
        return self._on_entity_removed

    @on_entity_removed.setter
    def on_entity_removed(self, value: Event[Entity]):
        pass  # __iadd__ modifies in place, setter is no-op

    def find_entity_by_uuid(self, uuid: str) -> Entity | None:
        """
        Find entity by UUID in the scene hierarchy.

        Searches through all entities and their children recursively.

        Args:
            uuid: The UUID to search for

        Returns:
            Entity with matching UUID or None if not found
        """
        for entity in self.entities:
            result = self._find_entity_by_uuid_recursive(entity, uuid)
            if result is not None:
                return result
        return None

    def _find_entity_by_uuid_recursive(self, entity: Entity, uuid: str) -> Entity | None:
        """Recursive helper for find_entity_by_uuid."""
        if entity.uuid == uuid:
            return entity
        for child in entity.children():
            result = self._find_entity_by_uuid_recursive(child, uuid)
            if result is not None:
                return result
        return None

    # --- Component search ---

    def find_component(self, component_type: type) -> Component | None:
        """
        Find first component of given type in scene.

        Args:
            component_type: Component class to search for.

        Returns:
            First matching component or None.
        """
        for entity in self.entities:
            comp = entity.get_component(component_type)
            if comp is not None:
                return comp
        return None

    def find_components(self, component_type: type) -> List[Component]:
        """
        Find all components of given type in scene.

        Args:
            component_type: Component class to search for.

        Returns:
            List of all matching components.
        """
        result = []
        for entity in self.entities:
            comp = entity.get_component(component_type)
            if comp is not None:
                result.append(comp)
        return result

    def find_component_by_name(self, class_name: str) -> Component | None:
        """
        Find first component by class name string.

        Args:
            class_name: Name of the component class (e.g. "TweenManagerComponent").

        Returns:
            First matching component or None.
        """
        for entity in self.entities:
            for comp in entity.components:
                if type(comp).__name__ == class_name:
                    return comp
        return None

    # --- Component registration ---

    def register_component(self, component: Component):
        from termin.colliders.collider_component import ColliderComponent

        if isinstance(component, ColliderComponent):
            self.colliders.append(component)

        if isinstance(component, LightComponent):
            self._lighting.register_light_component(component)

        if isinstance(component, InputComponent):
            self._input_components.append(component)

        # For native C++ components, use flags set by REGISTER_COMPONENT
        # For Python components, check if method is overridden and set flags
        if not component.is_native:
            if is_overrides_method(component, "update", Component):
                component.has_update = True
            if is_overrides_method(component, "fixed_update", Component):
                component.has_fixed_update = True

        # Sync flags to C component and register with TcScene
        component.sync_to_c()
        self._tc_scene.register_component(component)

    def unregister_component(self, component: Component):
        from termin.colliders.collider_component import ColliderComponent

        if isinstance(component, ColliderComponent) and component in self.colliders:
            self.colliders.remove(component)

        if isinstance(component, LightComponent):
            self._lighting.unregister_light_component(component)

        if isinstance(component, InputComponent) and component in self._input_components:
            self._input_components.remove(component)

        # Unregister from TcScene
        self._tc_scene.unregister_component(component)

    # --- Update loop ---

    def update(self, dt: float):
        # Delegate to C core (includes profiling via tc_profiler)
        self._tc_scene.update(dt)

    def editor_update(self, dt: float):
        """
        Update only components with active_in_editor=True.

        Called in editor mode to run editor-specific components.
        Uses the same _started flag as regular update().
        """
        # Delegate to C core
        self._tc_scene.editor_update(dt)

    def notify_editor_start(self):
        """Notify all components that scene started in editor mode."""
        for entity in self.entities:
            for component in entity.components:
                component.on_editor_start()

    # --- Input dispatch ---

    def dispatch_input(self, event_name: str, event, filter_fn: Callable[[InputComponent], bool] | None = None):
        """Dispatch input event to InputComponents.

        Args:
            event_name: Name of the handler method (e.g., "on_mouse_button").
            event: Event object to dispatch.
            filter_fn: Optional filter function. If provided, only components
                       for which filter_fn(component) returns True receive the event.
        """
        listeners = list(self._input_components)
        for component in listeners:
            if filter_fn is not None and not filter_fn(component):
                continue
            handler = getattr(component, event_name, None)
            if handler:
                handler(event)

    # --- Serialization ---

    def serialize(self) -> dict:
        """
        Serialize the scene.

        Only saves root serializable entities (without parent).
        Child entities are serialized recursively inside their parents.
        """
        root_entities = [
            e for e in self.entities
            if e.transform.parent is None and e.serializable
        ]
        serialized_entities = []
        for e in root_entities:
            data = e.serialize()
            if data is not None:
                serialized_entities.append(data)

        result = {
            "uuid": self.uuid,
            "background_color": list(self.background_color),
            "entities": serialized_entities,
            "layer_names": {str(k): v for k, v in self.layer_names.items()},
            "flag_names": {str(k): v for k, v in self.flag_names.items()},
        }
        result.update(self._lighting.serialize())
        result.update(self._skybox.serialize())
        return result

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "Scene":
        """Deserialize a scene."""
        scene = cls(
            background_color=data.get("background_color", (0.05, 0.05, 0.08, 1.0)),
            uuid=data.get("uuid"),
        )
        scene.load_from_data(data, context, update_settings=True)
        return scene

    def load_from_data(self, data: dict, context=None, update_settings: bool = True) -> int:
        """
        Load data into existing scene.

        Parameters:
            data: Serialized scene data
            context: Deserialization context
            update_settings: Whether to update scene settings (background, light)

        Returns:
            Number of loaded entities
        """
        if update_settings:
            self.background_color = np.asarray(
                data.get("background_color", [0.05, 0.05, 0.08, 1.0]),
                dtype=np.float32
            )
            self._lighting.load_from_data(data)
            self._skybox.load_from_data(data)
            # Load layer and flag names
            self.layer_names = {int(k): v for k, v in data.get("layer_names", {}).items()}
            self.flag_names = {int(k): v for k, v in data.get("flag_names", {}).items()}

        entities_data = data.get("entities", [])
        for ent_data in entities_data:
            ent = self._deserialize_entity_recursive(ent_data, context)
            if ent:
                self.add(ent)

        return len(entities_data)
        
    def _deserialize_entity_recursive(self, data: dict, context=None) -> Entity | None:
        """Deserialize entity with children recursively."""
        ent = Entity.deserialize(data, context)
        if ent is None:
            return None

        # Deserialize children and set parent
        children_data = data.get("children", [])
        for child_data in children_data:
            child = self._deserialize_entity_recursive(child_data, context)
            if child:
                child.set_parent(ent)

        return ent
