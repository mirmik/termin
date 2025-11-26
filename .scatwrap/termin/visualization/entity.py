<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/entity.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Scene entity storing components (Unity-like architecture).&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
from dataclasses import dataclass, field<br>
from typing import Iterable, List, Optional, Type, TypeVar, TYPE_CHECKING<br>
<br>
import numpy as np<br>
<br>
from termin.geombase.pose3 import Pose3<br>
from termin.kinematic.transform import Transform3<br>
from .backends.base import GraphicsBackend<br>
<br>
if TYPE_CHECKING:  # pragma: no cover<br>
    from .camera import Camera<br>
    from .renderer import Renderer<br>
    from .scene import Scene<br>
    from .shader import ShaderProgram<br>
<br>
from termin.visualization.serialization import COMPONENT_REGISTRY<br>
from termin.visualization.inspect import InspectField<br>
<br>
<br>
@dataclass<br>
class RenderContext:<br>
    &quot;&quot;&quot;Data bundle passed to components during rendering.&quot;&quot;&quot;<br>
<br>
    view: np.ndarray<br>
    projection: np.ndarray<br>
    camera: &quot;Camera&quot;<br>
    scene: &quot;Scene&quot;<br>
    renderer: &quot;Renderer&quot;<br>
    context_key: int<br>
    graphics: GraphicsBackend<br>
    phase: str = &quot;main&quot;<br>
<br>
<br>
class Component:<br>
    &quot;&quot;&quot;Base class for all entity components.&quot;&quot;&quot;<br>
<br>
    def __init__(self, enabled: bool = True):<br>
        self.enabled = enabled<br>
        self.entity: Optional[&quot;Entity&quot;] = None<br>
        self._started = False<br>
<br>
    # Если None → компонент не сериализуется<br>
    serializable_fields = None<br>
<br>
    # Поля, которые инспектор может редактировать.<br>
    # Заполняется либо руками, либо через дескриптор InspectAttr.<br>
    inspect_fields: dict[str, InspectField] | None = None<br>
<br>
    def required_shaders(self) -&gt; Iterable[&quot;ShaderProgram&quot;]:<br>
        &quot;&quot;&quot;Return shaders that must be compiled before rendering.&quot;&quot;&quot;<br>
        return ()<br>
<br>
    def start(self, scene: &quot;Scene&quot;):<br>
        &quot;&quot;&quot;Called once when the component becomes part of an active scene.&quot;&quot;&quot;<br>
        self._started = True<br>
<br>
    def update(self, dt: float):<br>
        &quot;&quot;&quot;Called every frame.&quot;&quot;&quot;<br>
        return<br>
<br>
    def draw(self, context: RenderContext):<br>
        &quot;&quot;&quot;Issue draw calls.&quot;&quot;&quot;<br>
        return<br>
<br>
    def on_removed(self):<br>
        &quot;&quot;&quot;Called when component is removed from its entity.&quot;&quot;&quot;<br>
        return<br>
<br>
    # Если None → компонент не сериализуется<br>
    serializable_fields = None<br>
<br>
    def serialize_data(self):<br>
        if self._serializable_fields is None:<br>
            return None<br>
<br>
        result = {}<br>
        fields = self._serializable_fields<br>
<br>
        if isinstance(fields, dict):<br>
            for key, typ in fields.items():<br>
                value = getattr(self, key)<br>
                result[key] = typ.serialize(value) if typ else value<br>
        else:<br>
            for key in fields:<br>
                result[key] = getattr(self, key)<br>
<br>
        return result<br>
<br>
    def serialize(self):<br>
        data = self.serialize_data()<br>
        return {<br>
            &quot;data&quot;: data,<br>
            &quot;type&quot;: self.__class__.__name__,<br>
        }<br>
        <br>
    @classmethod<br>
    def deserialize(cls, data, context):<br>
        obj = cls.__new__(cls)<br>
        cls.__init__(obj)<br>
<br>
        fields = cls._serializable_fields<br>
        if isinstance(fields, dict):<br>
            for key, typ in fields.items():<br>
                value = data[key]<br>
                setattr(obj, key, typ.deserialize(value, context) if typ else value)<br>
        else:<br>
            for key in fields:<br>
                setattr(obj, key, data[key])<br>
<br>
        return obj<br>
<br>
<br>
class InputComponent(Component):<br>
    &quot;&quot;&quot;Component capable of handling input events.&quot;&quot;&quot;<br>
<br>
    def on_mouse_button(self, viewport, button: int, action: int, mods: int):<br>
        return<br>
<br>
    def on_mouse_move(self, viewport, x: float, y: float, dx: float, dy: float):<br>
        return<br>
<br>
    def on_scroll(self, viewport, xoffset: float, yoffset: float):<br>
        return<br>
<br>
    def on_key(self, viewport, key: int, scancode: int, action: int, mods: int):<br>
        return<br>
<br>
<br>
C = TypeVar(&quot;C&quot;, bound=Component)<br>
<br>
<br>
class Entity:<br>
    &quot;&quot;&quot;Container of components with transform data.&quot;&quot;&quot;<br>
<br>
    def __init__(self, pose: Pose3 = Pose3.identity(), name : str = &quot;entity&quot;, scale: float = 1.0, priority: int = 0, <br>
            pickable: bool = True,<br>
            selectable: bool = True):<br>
        self.transform = Transform3(pose)<br>
        self.transform.entity = self<br>
        self.visible = True<br>
        self.active = True<br>
        self.name = name<br>
        self.scale = scale<br>
        self.priority = priority  # rendering priority, lower values drawn first<br>
        self._components: List[Component] = []<br>
        self.scene: Optional[&quot;Scene&quot;] = None<br>
        self.pickable = pickable       # &lt;--- и это<br>
        self.selectable = selectable       # &lt;--- и это<br>
<br>
    def __post_init__(self):<br>
        self.scene: Optional[&quot;Scene&quot;] = None<br>
        self._components: List[Component] = []<br>
<br>
    def model_matrix(self) -&gt; np.ndarray:<br>
        &quot;&quot;&quot;Construct homogeneous model matrix ``M = [R|t]`` with optional uniform scale.&quot;&quot;&quot;<br>
        matrix = self.transform.global_pose().as_matrix().copy()<br>
        matrix[:3, :3] *= self.scale<br>
        return matrix<br>
<br>
    def set_visible(self, flag: bool):<br>
        self.visible = flag<br>
        for child in self.transform.children:<br>
            if child.entity is not None:<br>
                child.entity.set_visible(flag)<br>
<br>
<br>
    def is_pickable(self) -&gt; bool:<br>
        return self.pickable and self.visible and self.active<br>
<br>
    def add_component(self, component: Component) -&gt; Component:<br>
        component.entity = self<br>
        self._components.append(component)<br>
        if self.scene is not None:<br>
            self.scene.register_component(component)<br>
            if not component._started:<br>
                component.start(self.scene)<br>
        return component<br>
<br>
    def remove_component(self, component: Component):<br>
        if component not in self._components:<br>
            return<br>
        self._components.remove(component)<br>
        if self.scene is not None:<br>
            self.scene.unregister_component(component)<br>
        component.on_removed()<br>
        component.entity = None<br>
<br>
    def get_component(self, component_type: Type[C]) -&gt; Optional[C]:<br>
        for comp in self._components:<br>
            if isinstance(comp, component_type):<br>
                return comp<br>
        return None<br>
<br>
    def find_component(self, component_type: Type[C]) -&gt; C:<br>
        comp = self.get_component(component_type)<br>
        if comp is None:<br>
            raise ValueError(f&quot;Component of type {component_type} not found in entity {self.name}&quot;)<br>
        return comp<br>
<br>
    @property<br>
    def components(self) -&gt; List[Component]:<br>
        return list(self._components)<br>
<br>
    def update(self, dt: float):<br>
        if not self.active:<br>
            return<br>
        for component in self._components:<br>
            if component.enabled:<br>
                component.update(dt)<br>
<br>
    def draw(self, context: RenderContext):<br>
        if not (self.active and self.visible):<br>
            return<br>
        for component in self._components:<br>
            if component.enabled:<br>
                component.draw(context)<br>
<br>
    def gather_shaders(self) -&gt; Iterable[&quot;ShaderProgram&quot;]:<br>
        for component in self._components:<br>
            yield from component.required_shaders()<br>
<br>
    def on_added(self, scene: &quot;Scene&quot;):<br>
        self.scene = scene<br>
        for component in self._components:<br>
            scene.register_component(component)<br>
            if not component._started:<br>
                component.start(scene)<br>
<br>
    def on_removed(self):<br>
        for component in self._components:<br>
            if self.scene is not None:<br>
                self.scene.unregister_component(component)<br>
            component.on_removed()<br>
            component.entity = None<br>
        self.scene = None<br>
<br>
    def serialize(self):<br>
        pose = self.transform.local_pose()<br>
<br>
        return {<br>
            &quot;name&quot;: self.name,<br>
            &quot;priority&quot;: self.priority,<br>
            &quot;scale&quot;: self.scale,<br>
            &quot;pose&quot;: {<br>
                &quot;position&quot;: pose.lin.tolist(),<br>
                &quot;rotation&quot;: pose.ang.tolist(),<br>
            },<br>
            &quot;components&quot;: [<br>
                comp.serialize()<br>
                for comp in self.components<br>
                if comp.serialize() is not None<br>
            ]<br>
        }<br>
<br>
    @classmethod<br>
    def deserialize(cls, data, context):<br>
        import numpy as np<br>
        from termin.geombase.pose3 import Pose3<br>
<br>
        ent = cls(<br>
            pose=Pose3(<br>
                lin=np.array(data[&quot;pose&quot;][&quot;position&quot;]),<br>
                ang=np.array(data[&quot;pose&quot;][&quot;rotation&quot;]),<br>
            ),<br>
            name=data[&quot;name&quot;],<br>
            scale=data[&quot;scale&quot;],<br>
            priority=data[&quot;priority&quot;],<br>
        )<br>
<br>
        for c in data[&quot;components&quot;]:<br>
            comp_cls = COMPONENT_REGISTRY[c[&quot;type&quot;]]<br>
            comp = comp_cls.deserialize(c[&quot;data&quot;], context)<br>
            ent.add_component(comp)<br>
<br>
        return ent<br>
<!-- END SCAT CODE -->
</body>
</html>
