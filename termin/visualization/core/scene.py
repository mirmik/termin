"""Simple scene graph storing entities and global parameters."""

from __future__ import annotations

from typing import List, Sequence, TYPE_CHECKING

import numpy as np

from termin.visualization.core.entity import Component, Entity, InputComponent
from termin.visualization.render.components.light_component import LightComponent
from termin.visualization.platform.backends.base import GraphicsBackend
from termin.geombase.ray import Ray3
from termin.colliders.raycast_hit import RaycastHit
from termin.colliders.collider_component import ColliderComponent


if TYPE_CHECKING:  # pragma: no cover
    from termin.visualization.render.shader import ShaderProgram

def is_overrides_method(obj, method_name, base_class):
    return getattr(obj.__class__, method_name) is not getattr(base_class, method_name)

class Scene:
    def raycast(self, ray: Ray3):
        """
        Возвращает первое пересечение с любым ColliderComponent,
        где distance == 0 (чистое попадание).
        """
        best_hit = None
        best_ray_dist = float("inf")

        for comp in self.colliders:
            attached = comp.attached
            if attached is None:
                continue

            p_col, p_ray, dist = attached.closest_to_ray(ray)

            # Интересуют только пересечения
            if dist != 0.0:
                continue

            # Реальное расстояние вдоль луча
            d_ray = np.linalg.norm(p_ray - ray.origin)

            if d_ray < best_ray_dist:
                best_ray_dist = d_ray
                best_hit = RaycastHit(comp.entity, comp, p_ray, p_col, 0.0)

        return best_hit

    def closest_to_ray(self, ray: Ray3):
        """
        Возвращает ближайший объект к лучу (минимальная distance).
        Не требует пересечения.
        """
        best_hit = None
        best_dist = float("inf")

        for comp in self.colliders:
            attached = comp.attached
            if attached is None:
                continue

            p_col, p_ray, dist = attached.closest_to_ray(ray)

            if dist < best_dist:
                best_dist = dist
                best_hit = RaycastHit(comp.entity, comp, p_ray, p_col, dist)

        return best_hit

    """Container for renderable entities and lighting data."""
    def __init__(self, background_color: Sequence[float] = (0.05, 0.05, 0.08, 1.0)):
        self.entities: List[Entity] = []
        self.lights: List[np.ndarray] = []
        self.background_color = np.array(background_color, dtype=np.float32)
        self._shaders_set = set()
        self._inited = False
        self._input_components: List[InputComponent] = []
        self._graphics: GraphicsBackend | None = None
        self.colliders = []
        self.light_components: List[LightComponent] = []
        self.update_list: List[Component] = []

        # Lights
        self.light_direction = np.array([-0.5, -1.0, -0.3], dtype=np.float32)
        self.light_color = np.array([1.0, 1.0, 1.0], dtype=np.float32)

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

    def register_component(self, component: Component):
        # регистрируем коллайдеры
        from termin.colliders.collider_component import ColliderComponent

        if isinstance(component, ColliderComponent):
            self.colliders.append(component)

        # регистрируем компоненты освещения
        if isinstance(component, LightComponent):
            self.light_components.append(component)

        for shader in component.required_shaders():
            self._register_shader(shader)

        if isinstance(component, InputComponent):
            self._input_components.append(component)

        if is_overrides_method(component, "update", Component):
            self.update_list.append(component)

    def unregister_component(self, component: Component):
        from termin.colliders.collider_component import ColliderComponent

        if isinstance(component, ColliderComponent) and component in self.colliders:
            self.colliders.remove(component)

        if isinstance(component, LightComponent) and component in self.light_components:
            self.light_components.remove(component)

        if isinstance(component, InputComponent) and component in self._input_components:
            self._input_components.remove(component)

    def update(self, dt: float):
        for component in self.update_list:
            component.update(dt)

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

    def dispatch_input(self, viewport, event: str, **kwargs):
        listeners = list(self._input_components)
        for component in listeners:
            handler = getattr(component, event, None)
            if handler:
                handler(viewport, **kwargs)

    def serialize(self):
        return {
            "background_color": self.background_color.tolist(),
            "light_direction": self.light_direction.tolist(),
            "light_color": self.light_color.tolist(),
            "entities": [e.serialize() for e in self.entities]
        }

    @classmethod
    def deserialize(cls, data, context, EntityClass):
        scene = cls(background_color=data["background_color"])
        scene.light_direction = data["light_direction"]
        scene.light_color = data["light_color"]

        for ed in data["entities"]:
            ent = EntityClass.deserialize(ed, context)
            scene.add(ent)

        return scene
