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
    from .shader import ShaderProgram<br>
<br>
def is_overrides_method(obj, method_name, base_class):<br>
    return getattr(obj.__class__, method_name) is not getattr(base_class, method_name)<br>
<br>
class Scene:<br>
    def raycast(self, ray: Ray3):<br>
        &quot;&quot;&quot;<br>
        Возвращает первое пересечение с любым ColliderComponent,<br>
        где distance == 0 (чистое попадание).<br>
        &quot;&quot;&quot;<br>
        best_hit = None<br>
        best_ray_dist = float(&quot;inf&quot;)<br>
<br>
        for comp in self.colliders:<br>
            attached = comp.attached<br>
            if attached is None:<br>
                continue<br>
<br>
            p_col, p_ray, dist = attached.closest_to_ray(ray)<br>
<br>
            # Интересуют только пересечения<br>
            if dist != 0.0:<br>
                continue<br>
<br>
            # Реальное расстояние вдоль луча<br>
            d_ray = np.linalg.norm(p_ray - ray.origin)<br>
<br>
            if d_ray &lt; best_ray_dist:<br>
                best_ray_dist = d_ray<br>
                best_hit = RaycastHit(comp.entity, comp, p_ray, p_col, 0.0)<br>
<br>
        return best_hit<br>
<br>
    def closest_to_ray(self, ray: Ray3):<br>
        &quot;&quot;&quot;<br>
        Возвращает ближайший объект к лучу (минимальная distance).<br>
        Не требует пересечения.<br>
        &quot;&quot;&quot;<br>
        best_hit = None<br>
        best_dist = float(&quot;inf&quot;)<br>
<br>
        for comp in self.colliders:<br>
            attached = comp.attached<br>
            if attached is None:<br>
                continue<br>
<br>
            p_col, p_ray, dist = attached.closest_to_ray(ray)<br>
<br>
            if dist &lt; best_dist:<br>
                best_dist = dist<br>
                best_hit = RaycastHit(comp.entity, comp, p_ray, p_col, dist)<br>
<br>
        return best_hit<br>
<br>
    &quot;&quot;&quot;Container for renderable entities and lighting data.&quot;&quot;&quot;<br>
    def __init__(self, background_color: Sequence[float] = (0.05, 0.05, 0.08, 1.0)):<br>
        self.entities: List[Entity] = []<br>
        self.lights: List[np.ndarray] = []<br>
        self.background_color = np.array(background_color, dtype=np.float32)<br>
        self._shaders_set = set()<br>
        self._inited = False<br>
        self._input_components: List[InputComponent] = []<br>
        self._graphics: GraphicsBackend | None = None<br>
        self.colliders = []<br>
        self.update_list: List[Component] = []<br>
<br>
        # Lights<br>
        self.light_direction = np.array([-0.5, -1.0, -0.3], dtype=np.float32)<br>
        self.light_color = np.array([1.0, 1.0, 1.0], dtype=np.float32)<br>
<br>
    def add_non_recurse(self, entity: Entity) -&gt; Entity:<br>
        &quot;&quot;&quot;Add entity to the scene, keeping the entities list sorted by priority.&quot;&quot;&quot;<br>
        index = 0<br>
        while index &lt; len(self.entities) and self.entities[index].priority &lt;= entity.priority:<br>
            index += 1<br>
        self.entities.insert(index, entity)<br>
        entity.on_added(self)<br>
        for shader in entity.gather_shaders():<br>
            self._register_shader(shader)<br>
        return entity<br>
<br>
    def add(self, entity: Entity) -&gt; Entity:<br>
        &quot;&quot;&quot;Add entity to the scene, including all its children.&quot;&quot;&quot;<br>
        print(&quot;Scene: adding entity&quot;, entity.name, &quot;children: {}&quot;.format(len(entity.transform.children)))  # --- IGNORE ---<br>
        self.add_non_recurse(entity)<br>
        for child_trans in entity.transform.children:<br>
            child = child_trans.entity<br>
            print(&quot;Scene: adding child entity&quot;, child)<br>
            if child is None:<br>
                continue<br>
            for shader in child.gather_shaders():<br>
                self._register_shader(shader)<br>
            self.add(child)<br>
        return entity<br>
<br>
    def remove(self, entity: Entity):<br>
        self.entities.remove(entity)<br>
        entity.on_removed()<br>
<br>
    def register_component(self, component: Component):<br>
        # регистрируем коллайдеры<br>
        from termin.colliders.collider_component import ColliderComponent<br>
        if isinstance(component, ColliderComponent):<br>
            self.colliders.append(component)<br>
        for shader in component.required_shaders():<br>
            self._register_shader(shader)<br>
        if isinstance(component, InputComponent):<br>
            self._input_components.append(component)<br>
        if is_overrides_method(component, &quot;update&quot;, Component):<br>
            self.update_list.append(component)<br>
<br>
    def unregister_component(self, component: Component):<br>
        from termin.colliders.collider_component import ColliderComponent<br>
        if isinstance(component, ColliderComponent) and component in self.colliders:<br>
            self.colliders.remove(component)<br>
        if isinstance(component, InputComponent) and component in self._input_components:<br>
            self._input_components.remove(component)<br>
<br>
    def update(self, dt: float):<br>
        for component in self.update_list:<br>
            component.update(dt)<br>
<br>
    def ensure_ready(self, graphics: GraphicsBackend):<br>
        if self._inited:<br>
            return<br>
        self._graphics = graphics<br>
        for shader in list(self._shaders_set):<br>
            shader.ensure_ready(graphics)<br>
        self._inited = True<br>
<br>
    def _register_shader(self, shader: &quot;ShaderProgram&quot;):<br>
        if shader in self._shaders_set:<br>
            return<br>
        self._shaders_set.add(shader)<br>
        if self._inited and self._graphics is not None:<br>
            shader.ensure_ready(self._graphics)<br>
<br>
    def dispatch_input(self, viewport, event: str, **kwargs):<br>
        listeners = list(self._input_components)<br>
        for component in listeners:<br>
            handler = getattr(component, event, None)<br>
            if handler:<br>
                handler(viewport, **kwargs)<br>
<br>
    def serialize(self):<br>
        return {<br>
            &quot;background_color&quot;: self.background_color.tolist(),<br>
            &quot;light_direction&quot;: self.light_direction.tolist(),<br>
            &quot;light_color&quot;: self.light_color.tolist(),<br>
            &quot;entities&quot;: [e.serialize() for e in self.entities]<br>
        }<br>
<br>
    @classmethod<br>
    def deserialize(cls, data, context, EntityClass):<br>
        scene = cls(background_color=data[&quot;background_color&quot;])<br>
        scene.light_direction = data[&quot;light_direction&quot;]<br>
        scene.light_color = data[&quot;light_color&quot;]<br>
<br>
        for ed in data[&quot;entities&quot;]:<br>
            ent = EntityClass.deserialize(ed, context)<br>
            scene.add(ent)<br>
<br>
        return scene<br>
<!-- END SCAT CODE -->
</body>
</html>
