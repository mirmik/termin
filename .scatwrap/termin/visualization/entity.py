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
&#9;from .camera import Camera<br>
&#9;from .renderer import Renderer<br>
&#9;from .scene import Scene<br>
&#9;from .shader import ShaderProgram<br>
<br>
from termin.visualization.serialization import COMPONENT_REGISTRY<br>
from termin.visualization.inspect import InspectField<br>
<br>
<br>
@dataclass<br>
class RenderContext:<br>
&#9;&quot;&quot;&quot;Data bundle passed to components during rendering.&quot;&quot;&quot;<br>
<br>
&#9;view: np.ndarray<br>
&#9;projection: np.ndarray<br>
&#9;camera: &quot;Camera&quot;<br>
&#9;scene: &quot;Scene&quot;<br>
&#9;renderer: &quot;Renderer&quot;<br>
&#9;context_key: int<br>
&#9;graphics: GraphicsBackend<br>
&#9;phase: str = &quot;main&quot;<br>
<br>
<br>
class Component:<br>
&#9;&quot;&quot;&quot;Base class for all entity components.&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, enabled: bool = True):<br>
&#9;&#9;self.enabled = enabled<br>
&#9;&#9;self.entity: Optional[&quot;Entity&quot;] = None<br>
&#9;&#9;self._started = False<br>
<br>
&#9;# Если None → компонент не сериализуется<br>
&#9;serializable_fields = None<br>
<br>
&#9;# Поля, которые инспектор может редактировать.<br>
&#9;# Заполняется либо руками, либо через дескриптор InspectAttr.<br>
&#9;inspect_fields: dict[str, InspectField] | None = None<br>
<br>
&#9;def required_shaders(self) -&gt; Iterable[&quot;ShaderProgram&quot;]:<br>
&#9;&#9;&quot;&quot;&quot;Return shaders that must be compiled before rendering.&quot;&quot;&quot;<br>
&#9;&#9;return ()<br>
<br>
&#9;def start(self, scene: &quot;Scene&quot;):<br>
&#9;&#9;&quot;&quot;&quot;Called once when the component becomes part of an active scene.&quot;&quot;&quot;<br>
&#9;&#9;self._started = True<br>
<br>
&#9;def update(self, dt: float):<br>
&#9;&#9;&quot;&quot;&quot;Called every frame.&quot;&quot;&quot;<br>
&#9;&#9;return<br>
<br>
&#9;def draw(self, context: RenderContext):<br>
&#9;&#9;&quot;&quot;&quot;Issue draw calls.&quot;&quot;&quot;<br>
&#9;&#9;return<br>
<br>
&#9;def on_removed(self):<br>
&#9;&#9;&quot;&quot;&quot;Called when component is removed from its entity.&quot;&quot;&quot;<br>
&#9;&#9;return<br>
<br>
&#9;# Если None → компонент не сериализуется<br>
&#9;serializable_fields = None<br>
<br>
&#9;def serialize_data(self):<br>
&#9;&#9;if self._serializable_fields is None:<br>
&#9;&#9;&#9;return None<br>
<br>
&#9;&#9;result = {}<br>
&#9;&#9;fields = self._serializable_fields<br>
<br>
&#9;&#9;if isinstance(fields, dict):<br>
&#9;&#9;&#9;for key, typ in fields.items():<br>
&#9;&#9;&#9;&#9;value = getattr(self, key)<br>
&#9;&#9;&#9;&#9;result[key] = typ.serialize(value) if typ else value<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;for key in fields:<br>
&#9;&#9;&#9;&#9;result[key] = getattr(self, key)<br>
<br>
&#9;&#9;return result<br>
<br>
&#9;def serialize(self):<br>
&#9;&#9;data = self.serialize_data()<br>
&#9;&#9;return {<br>
&#9;&#9;&#9;&quot;data&quot;: data,<br>
&#9;&#9;&#9;&quot;type&quot;: self.__class__.__name__,<br>
&#9;&#9;}<br>
&#9;&#9;<br>
&#9;@classmethod<br>
&#9;def deserialize(cls, data, context):<br>
&#9;&#9;obj = cls.__new__(cls)<br>
&#9;&#9;cls.__init__(obj)<br>
<br>
&#9;&#9;fields = cls._serializable_fields<br>
&#9;&#9;if isinstance(fields, dict):<br>
&#9;&#9;&#9;for key, typ in fields.items():<br>
&#9;&#9;&#9;&#9;value = data[key]<br>
&#9;&#9;&#9;&#9;setattr(obj, key, typ.deserialize(value, context) if typ else value)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;for key in fields:<br>
&#9;&#9;&#9;&#9;setattr(obj, key, data[key])<br>
<br>
&#9;&#9;return obj<br>
<br>
<br>
class InputComponent(Component):<br>
&#9;&quot;&quot;&quot;Component capable of handling input events.&quot;&quot;&quot;<br>
<br>
&#9;def on_mouse_button(self, viewport, button: int, action: int, mods: int):<br>
&#9;&#9;return<br>
<br>
&#9;def on_mouse_move(self, viewport, x: float, y: float, dx: float, dy: float):<br>
&#9;&#9;return<br>
<br>
&#9;def on_scroll(self, viewport, xoffset: float, yoffset: float):<br>
&#9;&#9;return<br>
<br>
&#9;def on_key(self, viewport, key: int, scancode: int, action: int, mods: int):<br>
&#9;&#9;return<br>
<br>
<br>
C = TypeVar(&quot;C&quot;, bound=Component)<br>
<br>
<br>
class Entity:<br>
&#9;&quot;&quot;&quot;Container of components with transform data.&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, pose: Pose3 = Pose3.identity(), name : str = &quot;entity&quot;, scale: float = 1.0, priority: int = 0, <br>
&#9;&#9;&#9;pickable: bool = True,<br>
&#9;&#9;&#9;selectable: bool = True):<br>
&#9;&#9;self.transform = Transform3(pose)<br>
&#9;&#9;self.transform.entity = self<br>
&#9;&#9;self.visible = True<br>
&#9;&#9;self.active = True<br>
&#9;&#9;self.name = name<br>
&#9;&#9;self.scale = scale<br>
&#9;&#9;self.priority = priority  # rendering priority, lower values drawn first<br>
&#9;&#9;self._components: List[Component] = []<br>
&#9;&#9;self.scene: Optional[&quot;Scene&quot;] = None<br>
&#9;&#9;self.pickable = pickable       # &lt;--- и это<br>
&#9;&#9;self.selectable = selectable       # &lt;--- и это<br>
<br>
&#9;def __post_init__(self):<br>
&#9;&#9;self.scene: Optional[&quot;Scene&quot;] = None<br>
&#9;&#9;self._components: List[Component] = []<br>
<br>
&#9;def model_matrix(self) -&gt; np.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Construct homogeneous model matrix ``M = [R|t]`` with optional uniform scale.&quot;&quot;&quot;<br>
&#9;&#9;matrix = self.transform.global_pose().as_matrix().copy()<br>
&#9;&#9;matrix[:3, :3] *= self.scale<br>
&#9;&#9;return matrix<br>
<br>
&#9;def set_visible(self, flag: bool):<br>
&#9;&#9;self.visible = flag<br>
&#9;&#9;for child in self.transform.children:<br>
&#9;&#9;&#9;if child.entity is not None:<br>
&#9;&#9;&#9;&#9;child.entity.set_visible(flag)<br>
<br>
<br>
&#9;def is_pickable(self) -&gt; bool:<br>
&#9;&#9;return self.pickable and self.visible and self.active<br>
<br>
&#9;def add_component(self, component: Component) -&gt; Component:<br>
&#9;&#9;component.entity = self<br>
&#9;&#9;self._components.append(component)<br>
&#9;&#9;if self.scene is not None:<br>
&#9;&#9;&#9;self.scene.register_component(component)<br>
&#9;&#9;&#9;if not component._started:<br>
&#9;&#9;&#9;&#9;component.start(self.scene)<br>
&#9;&#9;return component<br>
<br>
&#9;def remove_component(self, component: Component):<br>
&#9;&#9;if component not in self._components:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;self._components.remove(component)<br>
&#9;&#9;if self.scene is not None:<br>
&#9;&#9;&#9;self.scene.unregister_component(component)<br>
&#9;&#9;component.on_removed()<br>
&#9;&#9;component.entity = None<br>
<br>
&#9;def get_component(self, component_type: Type[C]) -&gt; Optional[C]:<br>
&#9;&#9;for comp in self._components:<br>
&#9;&#9;&#9;if isinstance(comp, component_type):<br>
&#9;&#9;&#9;&#9;return comp<br>
&#9;&#9;return None<br>
<br>
&#9;def find_component(self, component_type: Type[C]) -&gt; C:<br>
&#9;&#9;comp = self.get_component(component_type)<br>
&#9;&#9;if comp is None:<br>
&#9;&#9;&#9;raise ValueError(f&quot;Component of type {component_type} not found in entity {self.name}&quot;)<br>
&#9;&#9;return comp<br>
<br>
&#9;@property<br>
&#9;def components(self) -&gt; List[Component]:<br>
&#9;&#9;return list(self._components)<br>
<br>
&#9;def update(self, dt: float):<br>
&#9;&#9;if not self.active:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;for component in self._components:<br>
&#9;&#9;&#9;if component.enabled:<br>
&#9;&#9;&#9;&#9;component.update(dt)<br>
<br>
&#9;def draw(self, context: RenderContext):<br>
&#9;&#9;if not (self.active and self.visible):<br>
&#9;&#9;&#9;return<br>
&#9;&#9;for component in self._components:<br>
&#9;&#9;&#9;if component.enabled:<br>
&#9;&#9;&#9;&#9;component.draw(context)<br>
<br>
&#9;def gather_shaders(self) -&gt; Iterable[&quot;ShaderProgram&quot;]:<br>
&#9;&#9;for component in self._components:<br>
&#9;&#9;&#9;yield from component.required_shaders()<br>
<br>
&#9;def on_added(self, scene: &quot;Scene&quot;):<br>
&#9;&#9;self.scene = scene<br>
&#9;&#9;for component in self._components:<br>
&#9;&#9;&#9;scene.register_component(component)<br>
&#9;&#9;&#9;if not component._started:<br>
&#9;&#9;&#9;&#9;component.start(scene)<br>
<br>
&#9;def on_removed(self):<br>
&#9;&#9;for component in self._components:<br>
&#9;&#9;&#9;if self.scene is not None:<br>
&#9;&#9;&#9;&#9;self.scene.unregister_component(component)<br>
&#9;&#9;&#9;component.on_removed()<br>
&#9;&#9;&#9;component.entity = None<br>
&#9;&#9;self.scene = None<br>
<br>
&#9;def serialize(self):<br>
&#9;&#9;pose = self.transform.local_pose()<br>
<br>
&#9;&#9;return {<br>
&#9;&#9;&#9;&quot;name&quot;: self.name,<br>
&#9;&#9;&#9;&quot;priority&quot;: self.priority,<br>
&#9;&#9;&#9;&quot;scale&quot;: self.scale,<br>
&#9;&#9;&#9;&quot;pose&quot;: {<br>
&#9;&#9;&#9;&#9;&quot;position&quot;: pose.lin.tolist(),<br>
&#9;&#9;&#9;&#9;&quot;rotation&quot;: pose.ang.tolist(),<br>
&#9;&#9;&#9;},<br>
&#9;&#9;&#9;&quot;components&quot;: [<br>
&#9;&#9;&#9;&#9;comp.serialize()<br>
&#9;&#9;&#9;&#9;for comp in self.components<br>
&#9;&#9;&#9;&#9;if comp.serialize() is not None<br>
&#9;&#9;&#9;]<br>
&#9;&#9;}<br>
<br>
&#9;@classmethod<br>
&#9;def deserialize(cls, data, context):<br>
&#9;&#9;import numpy as np<br>
&#9;&#9;from termin.geombase.pose3 import Pose3<br>
<br>
&#9;&#9;ent = cls(<br>
&#9;&#9;&#9;pose=Pose3(<br>
&#9;&#9;&#9;&#9;lin=np.array(data[&quot;pose&quot;][&quot;position&quot;]),<br>
&#9;&#9;&#9;&#9;ang=np.array(data[&quot;pose&quot;][&quot;rotation&quot;]),<br>
&#9;&#9;&#9;),<br>
&#9;&#9;&#9;name=data[&quot;name&quot;],<br>
&#9;&#9;&#9;scale=data[&quot;scale&quot;],<br>
&#9;&#9;&#9;priority=data[&quot;priority&quot;],<br>
&#9;&#9;)<br>
<br>
&#9;&#9;for c in data[&quot;components&quot;]:<br>
&#9;&#9;&#9;comp_cls = COMPONENT_REGISTRY[c[&quot;type&quot;]]<br>
&#9;&#9;&#9;comp = comp_cls.deserialize(c[&quot;data&quot;], context)<br>
&#9;&#9;&#9;ent.add_component(comp)<br>
<br>
&#9;&#9;return ent<br>
<!-- END SCAT CODE -->
</body>
</html>
