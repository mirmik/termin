<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/scene.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Simple scene graph storing entities and global parameters.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
from typing import List, Sequence, TYPE_CHECKING<br>
<br>
import numpy as np<br>
<br>
from .entity import Component, Entity, InputComponent<br>
from .backends.base import GraphicsBackend<br>
<br>
from termin.geombase.ray import Ray3<br>
from termin.colliders.raycast_hit import RaycastHit<br>
from termin.colliders.collider_component import ColliderComponent<br>
<br>
<br>
<br>
if TYPE_CHECKING:  # pragma: no cover<br>
&#9;from .shader import ShaderProgram<br>
<br>
def is_overrides_method(obj, method_name, base_class):<br>
&#9;return getattr(obj.__class__, method_name) is not getattr(base_class, method_name)<br>
<br>
class Scene:<br>
&#9;def raycast(self, ray: Ray3):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Возвращает первое пересечение с любым ColliderComponent,<br>
&#9;&#9;где distance == 0 (чистое попадание).<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;best_hit = None<br>
&#9;&#9;best_ray_dist = float(&quot;inf&quot;)<br>
<br>
&#9;&#9;for comp in self.colliders:<br>
&#9;&#9;&#9;attached = comp.attached<br>
&#9;&#9;&#9;if attached is None:<br>
&#9;&#9;&#9;&#9;continue<br>
<br>
&#9;&#9;&#9;p_col, p_ray, dist = attached.closest_to_ray(ray)<br>
<br>
&#9;&#9;&#9;# Интересуют только пересечения<br>
&#9;&#9;&#9;if dist != 0.0:<br>
&#9;&#9;&#9;&#9;continue<br>
<br>
&#9;&#9;&#9;# Реальное расстояние вдоль луча<br>
&#9;&#9;&#9;d_ray = np.linalg.norm(p_ray - ray.origin)<br>
<br>
&#9;&#9;&#9;if d_ray &lt; best_ray_dist:<br>
&#9;&#9;&#9;&#9;best_ray_dist = d_ray<br>
&#9;&#9;&#9;&#9;best_hit = RaycastHit(comp.entity, comp, p_ray, p_col, 0.0)<br>
<br>
&#9;&#9;return best_hit<br>
<br>
&#9;def closest_to_ray(self, ray: Ray3):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Возвращает ближайший объект к лучу (минимальная distance).<br>
&#9;&#9;Не требует пересечения.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;best_hit = None<br>
&#9;&#9;best_dist = float(&quot;inf&quot;)<br>
<br>
&#9;&#9;for comp in self.colliders:<br>
&#9;&#9;&#9;attached = comp.attached<br>
&#9;&#9;&#9;if attached is None:<br>
&#9;&#9;&#9;&#9;continue<br>
<br>
&#9;&#9;&#9;p_col, p_ray, dist = attached.closest_to_ray(ray)<br>
<br>
&#9;&#9;&#9;if dist &lt; best_dist:<br>
&#9;&#9;&#9;&#9;best_dist = dist<br>
&#9;&#9;&#9;&#9;best_hit = RaycastHit(comp.entity, comp, p_ray, p_col, dist)<br>
<br>
&#9;&#9;return best_hit<br>
<br>
&#9;&quot;&quot;&quot;Container for renderable entities and lighting data.&quot;&quot;&quot;<br>
&#9;def __init__(self, background_color: Sequence[float] = (0.05, 0.05, 0.08, 1.0)):<br>
&#9;&#9;self.entities: List[Entity] = []<br>
&#9;&#9;self.lights: List[np.ndarray] = []<br>
&#9;&#9;self.background_color = np.array(background_color, dtype=np.float32)<br>
&#9;&#9;self._shaders_set = set()<br>
&#9;&#9;self._inited = False<br>
&#9;&#9;self._input_components: List[InputComponent] = []<br>
&#9;&#9;self._graphics: GraphicsBackend | None = None<br>
&#9;&#9;self.colliders = []<br>
&#9;&#9;self.update_list: List[Component] = []<br>
<br>
&#9;&#9;# Lights<br>
&#9;&#9;self.light_direction = np.array([-0.5, -1.0, -0.3], dtype=np.float32)<br>
&#9;&#9;self.light_color = np.array([1.0, 1.0, 1.0], dtype=np.float32)<br>
<br>
&#9;def add_non_recurse(self, entity: Entity) -&gt; Entity:<br>
&#9;&#9;&quot;&quot;&quot;Add entity to the scene, keeping the entities list sorted by priority.&quot;&quot;&quot;<br>
&#9;&#9;index = 0<br>
&#9;&#9;while index &lt; len(self.entities) and self.entities[index].priority &lt;= entity.priority:<br>
&#9;&#9;&#9;index += 1<br>
&#9;&#9;self.entities.insert(index, entity)<br>
&#9;&#9;entity.on_added(self)<br>
&#9;&#9;for shader in entity.gather_shaders():<br>
&#9;&#9;&#9;self._register_shader(shader)<br>
&#9;&#9;return entity<br>
<br>
&#9;def add(self, entity: Entity) -&gt; Entity:<br>
&#9;&#9;&quot;&quot;&quot;Add entity to the scene, including all its children.&quot;&quot;&quot;<br>
&#9;&#9;print(&quot;Scene: adding entity&quot;, entity.name, &quot;children: {}&quot;.format(len(entity.transform.children)))  # --- IGNORE ---<br>
&#9;&#9;self.add_non_recurse(entity)<br>
&#9;&#9;for child_trans in entity.transform.children:<br>
&#9;&#9;&#9;child = child_trans.entity<br>
&#9;&#9;&#9;print(&quot;Scene: adding child entity&quot;, child)<br>
&#9;&#9;&#9;if child is None:<br>
&#9;&#9;&#9;&#9;continue<br>
&#9;&#9;&#9;for shader in child.gather_shaders():<br>
&#9;&#9;&#9;&#9;self._register_shader(shader)<br>
&#9;&#9;&#9;self.add(child)<br>
&#9;&#9;return entity<br>
<br>
&#9;def remove(self, entity: Entity):<br>
&#9;&#9;self.entities.remove(entity)<br>
&#9;&#9;entity.on_removed()<br>
<br>
&#9;def register_component(self, component: Component):<br>
&#9;&#9;# регистрируем коллайдеры<br>
&#9;&#9;from termin.colliders.collider_component import ColliderComponent<br>
&#9;&#9;if isinstance(component, ColliderComponent):<br>
&#9;&#9;&#9;self.colliders.append(component)<br>
&#9;&#9;for shader in component.required_shaders():<br>
&#9;&#9;&#9;self._register_shader(shader)<br>
&#9;&#9;if isinstance(component, InputComponent):<br>
&#9;&#9;&#9;self._input_components.append(component)<br>
&#9;&#9;if is_overrides_method(component, &quot;update&quot;, Component):<br>
&#9;&#9;&#9;self.update_list.append(component)<br>
<br>
&#9;def unregister_component(self, component: Component):<br>
&#9;&#9;from termin.colliders.collider_component import ColliderComponent<br>
&#9;&#9;if isinstance(component, ColliderComponent) and component in self.colliders:<br>
&#9;&#9;&#9;self.colliders.remove(component)<br>
&#9;&#9;if isinstance(component, InputComponent) and component in self._input_components:<br>
&#9;&#9;&#9;self._input_components.remove(component)<br>
<br>
&#9;def update(self, dt: float):<br>
&#9;&#9;for component in self.update_list:<br>
&#9;&#9;&#9;component.update(dt)<br>
<br>
&#9;def ensure_ready(self, graphics: GraphicsBackend):<br>
&#9;&#9;if self._inited:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;self._graphics = graphics<br>
&#9;&#9;for shader in list(self._shaders_set):<br>
&#9;&#9;&#9;shader.ensure_ready(graphics)<br>
&#9;&#9;self._inited = True<br>
<br>
&#9;def _register_shader(self, shader: &quot;ShaderProgram&quot;):<br>
&#9;&#9;if shader in self._shaders_set:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;self._shaders_set.add(shader)<br>
&#9;&#9;if self._inited and self._graphics is not None:<br>
&#9;&#9;&#9;shader.ensure_ready(self._graphics)<br>
<br>
&#9;def dispatch_input(self, viewport, event: str, **kwargs):<br>
&#9;&#9;listeners = list(self._input_components)<br>
&#9;&#9;for component in listeners:<br>
&#9;&#9;&#9;handler = getattr(component, event, None)<br>
&#9;&#9;&#9;if handler:<br>
&#9;&#9;&#9;&#9;handler(viewport, **kwargs)<br>
<br>
&#9;def serialize(self):<br>
&#9;&#9;return {<br>
&#9;&#9;&#9;&quot;background_color&quot;: self.background_color.tolist(),<br>
&#9;&#9;&#9;&quot;light_direction&quot;: self.light_direction.tolist(),<br>
&#9;&#9;&#9;&quot;light_color&quot;: self.light_color.tolist(),<br>
&#9;&#9;&#9;&quot;entities&quot;: [e.serialize() for e in self.entities]<br>
&#9;&#9;}<br>
<br>
&#9;@classmethod<br>
&#9;def deserialize(cls, data, context, EntityClass):<br>
&#9;&#9;scene = cls(background_color=data[&quot;background_color&quot;])<br>
&#9;&#9;scene.light_direction = data[&quot;light_direction&quot;]<br>
&#9;&#9;scene.light_color = data[&quot;light_color&quot;]<br>
<br>
&#9;&#9;for ed in data[&quot;entities&quot;]:<br>
&#9;&#9;&#9;ent = EntityClass.deserialize(ed, context)<br>
&#9;&#9;&#9;scene.add(ent)<br>
<br>
&#9;&#9;return scene<br>
<!-- END SCAT CODE -->
</body>
</html>
