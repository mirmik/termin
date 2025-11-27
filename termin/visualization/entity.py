"""Scene entity storing components (Unity-like architecture)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Type, TypeVar, TYPE_CHECKING

import numpy as np

from termin.geombase.pose3 import Pose3
from termin.kinematic.transform import Transform3
from .backends.base import GraphicsBackend

if TYPE_CHECKING:  # pragma: no cover
    from .camera import Camera
    from .renderer import Renderer
    from .scene import Scene
    from .shader import ShaderProgram

from termin.visualization.serialization import COMPONENT_REGISTRY
from termin.visualization.inspect import InspectField


@dataclass
class RenderContext:
    """Data bundle passed to components during rendering."""

    view: np.ndarray
    projection: np.ndarray
    camera: "Camera"
    scene: "Scene"
    renderer: "Renderer"
    context_key: int
    graphics: GraphicsBackend
    phase: str = "main"


class Component:
    """Base class for all entity components."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.entity: Optional["Entity"] = None
        self._started = False

    # Если None → компонент не сериализуется
    serializable_fields = None

    # Поля, которые инспектор может редактировать.
    # Заполняется либо руками, либо через дескриптор InspectAttr.
    inspect_fields: dict[str, InspectField] | None = None

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

    # Если None → компонент не сериализуется
    serializable_fields = None

    def serialize_data(self):
        if self._serializable_fields is None:
            return None

        result = {}
        fields = self._serializable_fields

        if isinstance(fields, dict):
            for key, typ in fields.items():
                value = getattr(self, key)
                result[key] = typ.serialize(value) if typ else value
        else:
            for key in fields:
                result[key] = getattr(self, key)

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

        fields = cls._serializable_fields
        if isinstance(fields, dict):
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

    def __init__(self, pose: Pose3 = Pose3.identity(), name : str = "entity", scale: float | numpy.ndarray = 1.0, priority: int = 0, 
            pickable: bool = True,
            selectable: bool = True):
        print(f"Entity.__init__ called with scale={scale}")

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
        self.pickable = pickable       # <--- и это
        self.selectable = selectable       # <--- и это

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
                print(self._scale)


    def __post_init__(self):
        self.scene: Optional["Scene"] = None
        self._components: List[Component] = []

    def model_matrix(self) -> np.ndarray:
        """Construct homogeneous model matrix ``M = [R|t]`` with optional uniform scale."""
        matrix = self.transform.global_pose().as_matrix().copy()
        print(self._scale)
        matrix[:3, :3] = matrix[:3, :3] @ np.diag(self._scale)
        return matrix

    def set_visible(self, flag: bool):
        self.visible = flag
        for child in self.transform.children:
            if child.entity is not None:
                child.entity.set_visible(flag)


    def is_pickable(self) -> bool:
        return self.pickable and self.visible and self.active

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
        pose = self.transform.local_pose()
        return {
            "name": self.name,
            "priority": self.priority,
            "scale": self.scale.tolist(),   # было: self.scale
            "pose": {
                "position": pose.lin.tolist(),
                "rotation": pose.ang.tolist(),
            },
            "components": [
                comp.serialize()
                for comp in self.components
                if comp.serialize() is not None
            ],
        }


    @classmethod
    def deserialize(cls, data, context):
        import numpy as np
        from termin.geombase.pose3 import Pose3

        ent = cls(
            pose=Pose3(
                lin=np.array(data["pose"]["position"]),
                ang=np.array(data["pose"]["rotation"]),
            ),
            name=data["name"],
            scale=data["scale"],
            priority=data["priority"],
        )

        for c in data["components"]:
            comp_cls = COMPONENT_REGISTRY[c["type"]]
            comp = comp_cls.deserialize(c["data"], context)
            ent.add_component(comp)

        return ent