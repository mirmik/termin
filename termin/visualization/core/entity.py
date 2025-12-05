"""Scene entity storing components (Unity-like architecture)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Type, TypeVar, TYPE_CHECKING

import numpy as np

from termin.geombase.pose3 import Pose3
from termin.kinematic.transform import Transform3
from termin.visualization.platform.backends.base import GraphicsBackend
from termin.visualization.core.resources import ResourceManager

if TYPE_CHECKING:  # pragma: no cover
    from termin.visualization.core.camera import Camera
    from termin.visualization.render.renderer import Renderer
    from termin.visualization.core.scene import Scene
    from termin.visualization.render.shader import ShaderProgram

from termin.visualization.core.serialization import COMPONENT_REGISTRY
from termin.editor.inspect_field import InspectField


@dataclass
class RenderContext:
    """Data bundle passed to components during rendering."""

    view: np.ndarray
    projection: np.ndarray
    camera: "Camera"
    scene: "Scene"
    context_key: int
    graphics: GraphicsBackend
    phase: str = "main"
    
    # Shadow mapping данные (опционально, заполняется ColorPass)
    shadow_data: "ShadowMapArray | None" = None


class Component:
    """Base class for all entity components."""

    # Если None → компонент не сериализуется
    serializable_fields = None

    # Поля, которые инспектор может редактировать.
    # Заполняется либо руками, либо через дескриптор InspectAttr.
    inspect_fields: dict[str, InspectField] | None = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Базовый класс сам себя не регистрирует
        if cls is Component:
            return
        manager = ResourceManager.instance()
        manager.register_component(cls.__name__, cls)

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.entity: Optional["Entity"] = None
        self._started = False

    def required_shaders(self) -> Iterable["ShaderProgram"]:
        """Return shaders that must be compiled before rendering."""
        return ()

    def start(self, scene: "Scene"):
        """Called once when the component becomes part of an active scene."""
        self._started = True

    def update(self, dt: float):
        """Called every frame."""
        return

    def draw(self, context: RenderContext):
        """Issue draw calls."""
        return

    def on_removed(self):
        """Called when component is removed from its entity."""
        return

    def serialize_data(self):
        fields = self.serializable_fields
        inspect_fields = self.inspect_fields

        if fields is None and not inspect_fields:
            return None

        result = {}
        if isinstance(fields, dict):
            for key, typ in fields.items():
                value = getattr(self, key)
                result[key] = typ.serialize(value) if typ else value
        elif fields is not None:
            for key in fields:
                result[key] = getattr(self, key)

        if inspect_fields:
            for name, field in inspect_fields.items():
                if field.non_serializable:
                    continue
                key = field.path if field.path is not None else name
                if key in result:
                    continue
                result[key] = field.get_value(self)

        return result

    def serialize(self):
        data = self.serialize_data()
        return {
            "data": data,
            "type": self.__class__.__name__,
        }

    @classmethod
    def deserialize(cls, data, context):
        obj = cls.__new__(cls)
        cls.__init__(obj)

        fields = cls.serializable_fields
        if fields is None:
            pass  # Нет полей для десериализации
        elif isinstance(fields, dict):
            for key, typ in fields.items():
                value = data[key]
                setattr(obj, key, typ.deserialize(value, context) if typ else value)
        else:
            for key in fields:
                setattr(obj, key, data[key])

        return obj


class InputComponent(Component):
    """Component capable of handling input events."""

    def on_mouse_button(self, viewport, button: int, action: int, mods: int):
        return

    def on_mouse_move(self, viewport, x: float, y: float, dx: float, dy: float):
        return

    def on_scroll(self, viewport, xoffset: float, yoffset: float):
        return

    def on_key(self, viewport, key: int, scancode: int, action: int, mods: int):
        return


C = TypeVar("C", bound=Component)


class Entity:
    """Container of components with transform data."""

    _next_pick_id: int = 1
    _entities_by_pick_id: dict[int, "Entity"] = {}

    def __init__(self, pose: Pose3 = Pose3.identity(), name : str = "entity", scale: float | numpy.ndarray = 1.0, priority: int = 0,
            pickable: bool = True,
            selectable: bool = True,
            serializable: bool = True):

        if scale is None:
            scale = np.array([1.0, 1.0, 1.0], dtype=np.float32)

        self.transform = Transform3(pose)
        self.transform.entity = self
        self.visible = True
        self.active = True
        self.name = name
        self._scale: np.ndarray = np.array([1.0, 1.0, 1.0], dtype=float)
        self.scale = scale # вызов сеттера
        self.priority = priority  # rendering priority, lower values drawn first
        self._components: List[Component] = []
        self.scene: Optional["Scene"] = None
        self.pickable = pickable
        self.selectable = selectable
        self.serializable = serializable  # False для редакторных сущностей (гизмо и т.д.)
        self._pick_id: int | None = None

    @property
    def scale(self) -> np.ndarray:
        return self._scale

    @scale.setter
    def scale(self, value):
        if isinstance(value, (int, float)):
            arr = np.full(3, float(value), dtype=float)
        else:
            arr = np.array(value, dtype=float)

            # скаляр → [s, s, s]
            if arr.shape == ():
                arr = np.full(3, float(arr), dtype=float)
            elif arr.shape != (3,):
                raise ValueError(f"Entity.scale must be scalar or length-3, got shape {arr.shape}")

        self._scale = arr


    def __post_init__(self):
        self.scene: Optional["Scene"] = None
        self._components: List[Component] = []

    def model_matrix(self) -> np.ndarray:
        """Construct homogeneous model matrix ``M = [R|t]`` with optional uniform scale."""
        matrix = self.transform.global_pose().as_matrix().copy()
        matrix[:3, :3] = matrix[:3, :3] @ np.diag(self._scale)
        return matrix

    def set_visible(self, flag: bool):
        self.visible = flag
        for child in self.transform.children:
            if child.entity is not None:
                child.entity.set_visible(flag)


    def is_pickable(self) -> bool:
        return self.pickable and self.visible and self.active

    @property
    def pick_id(self) -> int:
        """Уникальный идентификатор сущности для pick-проходов."""

        if self._pick_id is None:
            pid = Entity._next_pick_id
            Entity._next_pick_id += 1
            self._pick_id = pid
            Entity._entities_by_pick_id[pid] = self
        return self._pick_id

    @classmethod
    def lookup_by_pick_id(cls, pid: int) -> "Entity | None":
        return cls._entities_by_pick_id.get(pid)

    def add_component(self, component: Component) -> Component:
        component.entity = self
        self._components.append(component)
        if self.scene is not None:
            self.scene.register_component(component)
            if not component._started:
                component.start(self.scene)
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

    def draw(self, context: RenderContext):
        if not (self.active and self.visible):
            return
        for component in self._components:
            if component.enabled:
                component.draw(context)

    def gather_shaders(self) -> Iterable["ShaderProgram"]:
        for component in self._components:
            yield from component.required_shaders()

    def on_added(self, scene: "Scene"):
        self.scene = scene
        for component in self._components:
            scene.register_component(component)
            if not component._started:
                component.start(scene)

    def on_removed(self):
        for component in self._components:
            if self.scene is not None:
                self.scene.unregister_component(component)
            component.on_removed()
            component.entity = None
        self.scene = None

    def serialize(self):
        if not self.serializable:
            return None

        pose = self.transform.local_pose()
        data = {
            "name": self.name,
            "priority": self.priority,
            "scale": list(self.scale),
            "visible": self.visible,
            "active": self.active,
            "pickable": self.pickable,
            "selectable": self.selectable,
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
        import numpy as np
        from termin.geombase.pose3 import Pose3

        ent = cls(
            pose=Pose3(
                lin=np.array(data["pose"]["position"]),
                ang=np.array(data["pose"]["rotation"]),
            ),
            name=data["name"],
            scale=data.get("scale", 1.0),
            priority=data.get("priority", 0),
            pickable=data.get("pickable", True),
            selectable=data.get("selectable", True),
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
