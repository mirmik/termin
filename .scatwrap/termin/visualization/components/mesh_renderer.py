<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/components/mesh_renderer.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from __future__ import annotations<br>
<br>
from typing import Iterable, Optional<br>
<br>
import numpy as np<br>
<br>
from ..entity import Component, RenderContext<br>
from ..mesh import MeshDrawable<br>
from termin.mesh.mesh import Mesh3<br>
from termin.geombase.pose3 import Pose3<br>
from termin.visualization.renderpass import RenderState, RenderPass<br>
from termin.visualization.inspect import InspectField<br>
from termin.visualization.material import Material<br>
<br>
class MeshRenderer(Component):<br>
&#9;&quot;&quot;&quot;Renderer component that draws MeshDrawable with one or multiple passes.&quot;&quot;&quot;<br>
<br>
&#9;inspect_fields = {<br>
&#9;&#9;# mesh-инспект мы уже добавляли раньше<br>
&#9;&#9;&quot;mesh&quot;: InspectField(<br>
&#9;&#9;&#9;path=&quot;mesh&quot;,<br>
&#9;&#9;&#9;label=&quot;Mesh&quot;,<br>
&#9;&#9;&#9;kind=&quot;mesh&quot;,<br>
&#9;&#9;&#9;# можно прямое присваивание, можно отдельный метод<br>
&#9;&#9;&#9;setter=lambda obj, value: obj.update_mesh(value),<br>
&#9;&#9;),<br>
&#9;&#9;&quot;material&quot;: InspectField(<br>
&#9;&#9;&#9;path=&quot;material&quot;,<br>
&#9;&#9;&#9;label=&quot;Material&quot;,<br>
&#9;&#9;&#9;kind=&quot;material&quot;,<br>
&#9;&#9;&#9;setter=lambda obj, value: obj.update_material(value),<br>
&#9;&#9;),<br>
&#9;}<br>
<br>
&#9;def __init__(<br>
&#9;&#9;self,<br>
&#9;&#9;mesh: MeshDrawable | None = None,<br>
&#9;&#9;material: Material | None = None,<br>
&#9;&#9;passes: list[RenderPass] | None = None,<br>
&#9;):<br>
&#9;&#9;super().__init__(enabled=True)<br>
<br>
&#9;&#9;if isinstance(mesh, Mesh3):<br>
&#9;&#9;&#9;mesh = MeshDrawable(mesh)<br>
<br>
&#9;&#9;self.mesh = mesh<br>
&#9;&#9;self.material = material<br>
<br>
&#9;&#9;self.passes: list[RenderPass] = []<br>
<br>
&#9;&#9;if passes is not None:<br>
&#9;&#9;&#9;# нормализация списка переданных проходов<br>
&#9;&#9;&#9;for p in passes:<br>
&#9;&#9;&#9;&#9;if isinstance(p, RenderPass):<br>
&#9;&#9;&#9;&#9;&#9;self.passes.append(p)<br>
&#9;&#9;&#9;&#9;elif isinstance(p, Material):<br>
&#9;&#9;&#9;&#9;&#9;self.passes.append(RenderPass(material=p, state=RenderState()))<br>
&#9;&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;&#9;raise TypeError(&quot;passes must contain Material or RenderPass&quot;)<br>
&#9;&#9;elif material is not None:<br>
&#9;&#9;&#9;# если материал задан в конструкторе — как раньше: один проход<br>
&#9;&#9;&#9;self.passes.append(RenderPass(material=material, state=RenderState()))<br>
<br>
&#9;def update_mesh(self, mesh: MeshDrawable | None):<br>
&#9;&#9;self.mesh = mesh<br>
<br>
&#9;def update_material(self, material: Material | None):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Вызывается инспектором при смене материала (и конструктором — косвенно).<br>
&#9;&#9;Гарантируем, что если появился материал, будет хотя бы один RenderPass.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.material = material<br>
<br>
&#9;&#9;if material is None:<br>
&#9;&#9;&#9;# Можно:<br>
&#9;&#9;&#9;#  - либо очищать материал у всех проходов,<br>
&#9;&#9;&#9;#  - либо вообще ничего не делать (но draw тогда должен уметь жить с этим).<br>
&#9;&#9;&#9;# Я бы для простоты просто обнулил материал в одиночном проходе.<br>
&#9;&#9;&#9;if len(self.passes) == 1:<br>
&#9;&#9;&#9;&#9;self.passes[0].material = None<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;if not self.passes:<br>
&#9;&#9;&#9;# Новый компонент, до этого не было проходов —<br>
&#9;&#9;&#9;# создаём дефолтный.<br>
&#9;&#9;&#9;self.passes.append(RenderPass(material=material, state=RenderState()))<br>
&#9;&#9;elif len(self.passes) == 1:<br>
&#9;&#9;&#9;# старый режим: один проход → просто обновляем материал<br>
&#9;&#9;&#9;self.passes[0].material = material<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;# мультипасс — решай сам, как надо делать:<br>
&#9;&#9;&#9;# можно менять только первый проход, можно все, можно вообще не трогать.<br>
&#9;&#9;&#9;self.passes[0].material = material<br>
<br>
&#9;# --- рендеринг ---<br>
<br>
&#9;def required_shaders(self):<br>
&#9;&#9;if self.material is None:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;for p in self.passes:<br>
&#9;&#9;&#9;yield p.material.shader<br>
<br>
&#9;def draw(self, context: RenderContext):<br>
&#9;&#9;if self.entity is None:<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;if self.mesh is None:<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;if self.material is None:<br>
&#9;&#9;&#9;return<br>
<br>
&#9;&#9;model = self.entity.model_matrix()<br>
&#9;&#9;view = context.view<br>
&#9;&#9;proj = context.projection<br>
&#9;&#9;gfx = context.graphics<br>
&#9;&#9;key = context.context_key<br>
<br>
&#9;&#9;for p in self.passes:<br>
&#9;&#9;&#9;gfx.apply_render_state(p.state)<br>
<br>
&#9;&#9;&#9;mat = p.material<br>
&#9;&#9;&#9;mat.apply(model, view, proj, graphics=gfx, context_key=key)<br>
<br>
&#9;&#9;&#9;shader = mat.shader<br>
<br>
&#9;&#9;&#9;if hasattr(context.scene, &quot;light_direction&quot;):<br>
&#9;&#9;&#9;&#9;shader.set_uniform_vec3(&quot;u_light_dir&quot;, context.scene.light_direction)<br>
&#9;&#9;&#9;if hasattr(context.scene, &quot;light_color&quot;):<br>
&#9;&#9;&#9;&#9;shader.set_uniform_vec3(&quot;u_light_color&quot;, context.scene.light_color)<br>
<br>
&#9;&#9;&#9;self.mesh.draw(context)<br>
<br>
&#9;&#9;gfx.apply_render_state(RenderState())<br>
<!-- END SCAT CODE -->
</body>
</html>
