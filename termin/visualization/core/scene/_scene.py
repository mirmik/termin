"""Simple scene graph storing entities and global parameters."""

from __future__ import annotations

from typing import List, Sequence, TYPE_CHECKING

import numpy as np

from termin.visualization.core.component import Component, InputComponent
from termin.visualization.core.entity import Entity
from termin.visualization.core.identifiable import Identifiable
from termin.visualization.core.lighting.light import Light
from termin.visualization.render.components.light_component import LightComponent
from termin.visualization.platform.backends.base import GraphicsBackend
from termin.geombase import Ray3
from termin.colliders.raycast_hit import RaycastHit
from termin.collision._collision_native import CollisionWorld

from .skybox import SkyboxManager
from .lighting import LightingManager


if TYPE_CHECKING:  # pragma: no cover
    from termin.visualization.render.shader import ShaderProgram
    from termin.visualization.core.mesh_handle import MeshHandle
    from termin.visualization.core.material import Material


def _vec3_to_np(v) -> np.ndarray:
    return np.array([v.x, v.y, v.z])


def is_overrides_method(obj, method_name, base_class):
    return getattr(obj.__class__, method_name) is not getattr(base_class, method_name)


class Scene(Identifiable):
    """Container for renderable entities and lighting data."""

    def __init__(
        self,
        background_color: Sequence[float] = (0.05, 0.05, 0.08, 1.0),
        uuid: str | None = None,
    ):
        super().__init__(uuid=uuid)
        self.entities: List[Entity] = []
        self.background_color = np.array(background_color, dtype=np.float32)
        self._shaders_set = set()
        self._inited = False
        self._input_components: List[InputComponent] = []
        self._graphics: GraphicsBackend | None = None
        self.colliders = []
        self._collision_world = CollisionWorld()
        self.update_list: List[Component] = []
        self._pending_start: List[Component] = []

        # Skybox manager
        self._skybox = SkyboxManager()

        # Lighting manager
        self._lighting = LightingManager()

        # Layer and flag names (index -> name)
        self.layer_names: dict[int, str] = {}  # 0-63
        self.flag_names: dict[int, str] = {}   # 0-63 (bit index)

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

    def add_non_recurse(self, entity: Entity) -> Entity:
        """Add entity to the scene, keeping the entities list sorted by priority."""
        index = 0
        while index < len(self.entities) and self.entities[index].priority <= entity.priority:
            index += 1
        self.entities.insert(index, entity)
        entity.on_added(self)
        for shader in entity.gather_shaders():
            self._register_shader(shader)
        return entity

    def add(self, entity: Entity) -> Entity:
        """Add entity to the scene, including all its children."""
        self.add_non_recurse(entity)
        for child_trans in entity.transform.children:
            child = child_trans.entity
            if child is None:
                continue
            for shader in child.gather_shaders():
                self._register_shader(shader)
            self.add(child)
        return entity

    def remove(self, entity: Entity):
        self.entities.remove(entity)
        entity.on_removed()

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
        for child_transform in entity.transform.children:
            child = child_transform.entity
            if child is not None:
                result = self._find_entity_by_uuid_recursive(child, uuid)
                if result is not None:
                    return result
        return None

    # --- Component registration ---

    def register_component(self, component: Component):
        from termin.colliders.collider_component import ColliderComponent

        if isinstance(component, ColliderComponent):
            self.colliders.append(component)

        if isinstance(component, LightComponent):
            self._lighting.register_light_component(component)

        for shader in component.required_shaders():
            self._register_shader(shader)

        if isinstance(component, InputComponent):
            self._input_components.append(component)

        if is_overrides_method(component, "update", Component):
            self.update_list.append(component)

        if not component._started:
            self._pending_start.append(component)

    def unregister_component(self, component: Component):
        from termin.colliders.collider_component import ColliderComponent

        if isinstance(component, ColliderComponent) and component in self.colliders:
            self.colliders.remove(component)

        if isinstance(component, LightComponent):
            self._lighting.unregister_light_component(component)

        if isinstance(component, InputComponent) and component in self._input_components:
            self._input_components.remove(component)

        if component in self.update_list:
            self.update_list.remove(component)

        if component in self._pending_start:
            self._pending_start.remove(component)

    # --- Update loop ---

    def update(self, dt: float):
        if self._pending_start:
            pending = self._pending_start
            self._pending_start = []
            for component in pending:
                if component._started:
                    continue
                if component.enabled:
                    component.start(self)
                else:
                    # Keep disabled components in pending until enabled
                    self._pending_start.append(component)

        for component in self.update_list:
            if component.enabled:
                component.update(dt)

    def notify_editor_start(self):
        """Notify all components that scene started in editor mode."""
        for entity in self.entities:
            for component in entity.components:
                component.on_editor_start()

    # --- Graphics initialization ---

    def ensure_ready(self, graphics: GraphicsBackend):
        if self._inited:
            return
        self._graphics = graphics
        for shader in list(self._shaders_set):
            shader.ensure_ready(graphics)
        self._inited = True

    def _register_shader(self, shader: "ShaderProgram"):
        if shader in self._shaders_set:
            return
        self._shaders_set.add(shader)
        if self._inited and self._graphics is not None:
            shader.ensure_ready(self._graphics)

    # --- Input dispatch ---

    def dispatch_input(self, event_name: str, event):
        """Dispatch input event to all InputComponents."""
        listeners = list(self._input_components)
        for component in listeners:
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

        loaded_count = 0
        for ent_data in data.get("entities", []):
            ent = Entity.deserialize(ent_data, context)
            self.add(ent)
            loaded_count += 1

        return loaded_count
