"""Simple scene graph storing entities and global parameters."""

from __future__ import annotations

from typing import List, Sequence, TYPE_CHECKING

import numpy as np

from termin.visualization.core.entity import Component, Entity, InputComponent
from termin.visualization.core.lighting.light import Light, LightType
from termin.visualization.render.components.light_component import LightComponent
from termin.visualization.platform.backends.base import GraphicsBackend
from termin.geombase.ray import Ray3
from termin.colliders.raycast_hit import RaycastHit
from termin.colliders.collider_component import ColliderComponent


if TYPE_CHECKING:  # pragma: no cover
    from termin.visualization.render.shader import ShaderProgram
    from termin.visualization.core.mesh import MeshDrawable
    from termin.visualization.core.material import Material

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
        self.lights: List[Light] = []
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

        # Ambient lighting (global, affects all surfaces uniformly)
        self.ambient_color = np.array([1.0, 1.0, 1.0], dtype=np.float32)
        self.ambient_intensity = 0.1

        # Skybox (lazily initialized)
        self._skybox_mesh: "MeshDrawable | None" = None
        self._skybox_material: "Material | None" = None
        self.skybox_type: str = "gradient"  # "gradient", "solid", "none"
        self.skybox_color = np.array([0.3, 0.5, 0.8], dtype=np.float32)  # for solid skybox
        self.skybox_top_color = np.array([0.05, 0.1, 0.25], dtype=np.float32)  # gradient top
        self.skybox_bottom_color = np.array([0.3, 0.3, 0.35], dtype=np.float32)  # gradient bottom

    def _ensure_skybox_mesh(self) -> "MeshDrawable":
        """Lazily create skybox cube mesh."""
        if self._skybox_mesh is None:
            from termin.visualization.core.mesh import MeshDrawable
            from termin.visualization.render.skybox import _skybox_cube
            vertices, triangles = _skybox_cube()
            self._skybox_mesh = MeshDrawable.from_vertices_indices(vertices, triangles)
        return self._skybox_mesh

    def _create_gradient_skybox_material(self) -> "Material":
        """Create gradient skybox material."""
        from termin.visualization.core.material import Material
        from termin.visualization.render.shader import ShaderProgram
        from termin.visualization.render.skybox import SKYBOX_VERTEX_SHADER, SKYBOX_FRAGMENT_SHADER
        shader = ShaderProgram(
            vertex_source=SKYBOX_VERTEX_SHADER,
            fragment_source=SKYBOX_FRAGMENT_SHADER,
        )
        material = Material(shader=shader)
        material.color = None
        return material

    def _create_solid_skybox_material(self) -> "Material":
        """Create solid color skybox material."""
        from termin.visualization.core.material import Material
        from termin.visualization.render.shader import ShaderProgram
        from termin.visualization.render.skybox import SKYBOX_VERTEX_SHADER, SKYBOX_SOLID_FRAGMENT_SHADER
        shader = ShaderProgram(
            vertex_source=SKYBOX_VERTEX_SHADER,
            fragment_source=SKYBOX_SOLID_FRAGMENT_SHADER,
        )
        material = Material(shader=shader)
        material.color = None
        return material

    def skybox_mesh(self) -> "MeshDrawable":
        """Get skybox cube mesh."""
        return self._ensure_skybox_mesh()

    def skybox_material(self) -> "Material | None":
        """Get skybox material based on current skybox_type."""
        if self.skybox_type == "none":
            return None
        if self._skybox_material is None:
            if self.skybox_type == "solid":
                self._skybox_material = self._create_solid_skybox_material()
            else:
                self._skybox_material = self._create_gradient_skybox_material()
        return self._skybox_material

    def set_skybox_type(self, skybox_type: str) -> None:
        """Set skybox type and reset material if type changed."""
        if self.skybox_type != skybox_type:
            self.skybox_type = skybox_type
            self._skybox_material = None  # force recreation

    def build_lights(self) -> List[Light]:
        """
        Собрать мировые параметры всех источников света.

        Направление локной оси ``-Z`` переносим в мир через поворот ``R`` сущности:
        ``dir_world = R * (0, 0, -1)``.
        """
        lights: list[Light] = []

        forward_local = np.array([0.0, 0.0, -1.0], dtype=np.float32)

        for comp in self.light_components:
            if not comp.enabled:
                continue
            if comp.entity is None:
                continue

            ent = comp.entity
            pose = ent.transform.global_pose()
            rotation = pose.rotation_matrix()

            position = np.asarray(pose.lin, dtype=np.float32)
            forward_world = np.asarray(rotation @ forward_local, dtype=np.float32)

            light = comp.to_light()
            light.position = position
            light.direction = forward_world
            lights.append(light)

        self.lights = lights
        return lights

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

        if component in self.update_list:
            self.update_list.remove(component)

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

    def serialize(self) -> dict:
        """
        Сериализует сцену.

        Сохраняет только корневые serializable Entity (без родителя).
        Дочерние Entity сериализуются рекурсивно внутри своих родителей.
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

        return {
            "background_color": list(self.background_color),
            "light_direction": list(self.light_direction),
            "light_color": list(self.light_color),
            "ambient_color": list(self.ambient_color),
            "ambient_intensity": self.ambient_intensity,
            "skybox_type": self.skybox_type,
            "skybox_color": list(self.skybox_color),
            "skybox_top_color": list(self.skybox_top_color),
            "skybox_bottom_color": list(self.skybox_bottom_color),
            "entities": serialized_entities,
        }

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "Scene":
        """Десериализует сцену."""
        scene = cls(background_color=data.get("background_color", (0.05, 0.05, 0.08, 1.0)))
        scene.load_from_data(data, context, update_settings=True)
        return scene

    def load_from_data(self, data: dict, context=None, update_settings: bool = True) -> int:
        """
        Загружает данные в существующую сцену.

        Параметры:
            data: Сериализованные данные сцены
            context: Контекст десериализации
            update_settings: Обновлять ли настройки сцены (background, light)

        Возвращает:
            Количество загруженных entities
        """
        if update_settings:
            self.background_color = np.asarray(
                data.get("background_color", [0.05, 0.05, 0.08, 1.0]),
                dtype=np.float32
            )
            self.light_direction = np.asarray(
                data.get("light_direction", [-0.5, -1.0, -0.3]),
                dtype=np.float32
            )
            self.light_color = np.asarray(
                data.get("light_color", [1.0, 1.0, 1.0]),
                dtype=np.float32
            )
            self.ambient_color = np.asarray(
                data.get("ambient_color", [1.0, 1.0, 1.0]),
                dtype=np.float32
            )
            self.ambient_intensity = data.get("ambient_intensity", 0.1)

            skybox_type = data.get("skybox_type", "gradient")
            self.set_skybox_type(skybox_type)
            self.skybox_color = np.asarray(
                data.get("skybox_color", [0.3, 0.5, 0.8]),
                dtype=np.float32
            )
            self.skybox_top_color = np.asarray(
                data.get("skybox_top_color", [0.05, 0.1, 0.25]),
                dtype=np.float32
            )
            self.skybox_bottom_color = np.asarray(
                data.get("skybox_bottom_color", [0.3, 0.3, 0.35]),
                dtype=np.float32
            )

        loaded_count = 0
        for ent_data in data.get("entities", []):
            ent = Entity.deserialize(ent_data, context)
            self.add(ent)
            loaded_count += 1

        return loaded_count
