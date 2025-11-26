<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/entity.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;Scene entity storing components (Unity-like architecture).&quot;&quot;&quot;

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
    &quot;&quot;&quot;Data bundle passed to components during rendering.&quot;&quot;&quot;

    view: np.ndarray
    projection: np.ndarray
    camera: &quot;Camera&quot;
    scene: &quot;Scene&quot;
    renderer: &quot;Renderer&quot;
    context_key: int
    graphics: GraphicsBackend
    phase: str = &quot;main&quot;


class Component:
    &quot;&quot;&quot;Base class for all entity components.&quot;&quot;&quot;

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.entity: Optional[&quot;Entity&quot;] = None
        self._started = False

    # Если None → компонент не сериализуется
    serializable_fields = None

    # Поля, которые инспектор может редактировать.
    # Заполняется либо руками, либо через дескриптор InspectAttr.
    inspect_fields: dict[str, InspectField] | None = None

    def required_shaders(self) -&gt; Iterable[&quot;ShaderProgram&quot;]:
        &quot;&quot;&quot;Return shaders that must be compiled before rendering.&quot;&quot;&quot;
        return ()

    def start(self, scene: &quot;Scene&quot;):
        &quot;&quot;&quot;Called once when the component becomes part of an active scene.&quot;&quot;&quot;
        self._started = True

    def update(self, dt: float):
        &quot;&quot;&quot;Called every frame.&quot;&quot;&quot;
        return

    def draw(self, context: RenderContext):
        &quot;&quot;&quot;Issue draw calls.&quot;&quot;&quot;
        return

    def on_removed(self):
        &quot;&quot;&quot;Called when component is removed from its entity.&quot;&quot;&quot;
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
            &quot;data&quot;: data,
            &quot;type&quot;: self.__class__.__name__,
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
    &quot;&quot;&quot;Component capable of handling input events.&quot;&quot;&quot;

    def on_mouse_button(self, viewport, button: int, action: int, mods: int):
        return

    def on_mouse_move(self, viewport, x: float, y: float, dx: float, dy: float):
        return

    def on_scroll(self, viewport, xoffset: float, yoffset: float):
        return

    def on_key(self, viewport, key: int, scancode: int, action: int, mods: int):
        return


C = TypeVar(&quot;C&quot;, bound=Component)


class Entity:
    &quot;&quot;&quot;Container of components with transform data.&quot;&quot;&quot;

    def __init__(self, pose: Pose3 = Pose3.identity(), name : str = &quot;entity&quot;, scale: float = 1.0, priority: int = 0, 
            pickable: bool = True,
            selectable: bool = True):
        self.transform = Transform3(pose)
        self.transform.entity = self
        self.visible = True
        self.active = True
        self.name = name
        self.scale = scale
        self.priority = priority  # rendering priority, lower values drawn first
        self._components: List[Component] = []
        self.scene: Optional[&quot;Scene&quot;] = None
        self.pickable = pickable       # &lt;--- и это
        self.selectable = selectable       # &lt;--- и это

    def __post_init__(self):
        self.scene: Optional[&quot;Scene&quot;] = None
        self._components: List[Component] = []

    def model_matrix(self) -&gt; np.ndarray:
        &quot;&quot;&quot;Construct homogeneous model matrix ``M = [R|t]`` with optional uniform scale.&quot;&quot;&quot;
        matrix = self.transform.global_pose().as_matrix().copy()
        matrix[:3, :3] *= self.scale
        return matrix

    def set_visible(self, flag: bool):
        self.visible = flag
        for child in self.transform.children:
            if child.entity is not None:
                child.entity.set_visible(flag)


    def is_pickable(self) -&gt; bool:
        return self.pickable and self.visible and self.active

    def add_component(self, component: Component) -&gt; Component:
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

    def get_component(self, component_type: Type[C]) -&gt; Optional[C]:
        for comp in self._components:
            if isinstance(comp, component_type):
                return comp
        return None

    def find_component(self, component_type: Type[C]) -&gt; C:
        comp = self.get_component(component_type)
        if comp is None:
            raise ValueError(f&quot;Component of type {component_type} not found in entity {self.name}&quot;)
        return comp

    @property
    def components(self) -&gt; List[Component]:
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

    def gather_shaders(self) -&gt; Iterable[&quot;ShaderProgram&quot;]:
        for component in self._components:
            yield from component.required_shaders()

    def on_added(self, scene: &quot;Scene&quot;):
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
            &quot;name&quot;: self.name,
            &quot;priority&quot;: self.priority,
            &quot;scale&quot;: self.scale,
            &quot;pose&quot;: {
                &quot;position&quot;: pose.lin.tolist(),
                &quot;rotation&quot;: pose.ang.tolist(),
            },
            &quot;components&quot;: [
                comp.serialize()
                for comp in self.components
                if comp.serialize() is not None
            ]
        }

    @classmethod
    def deserialize(cls, data, context):
        import numpy as np
        from termin.geombase.pose3 import Pose3

        ent = cls(
            pose=Pose3(
                lin=np.array(data[&quot;pose&quot;][&quot;position&quot;]),
                ang=np.array(data[&quot;pose&quot;][&quot;rotation&quot;]),
            ),
            name=data[&quot;name&quot;],
            scale=data[&quot;scale&quot;],
            priority=data[&quot;priority&quot;],
        )

        for c in data[&quot;components&quot;]:
            comp_cls = COMPONENT_REGISTRY[c[&quot;type&quot;]]
            comp = comp_cls.deserialize(c[&quot;data&quot;], context)
            ent.add_component(comp)

        return ent
</code></pre>
</body>
</html>
