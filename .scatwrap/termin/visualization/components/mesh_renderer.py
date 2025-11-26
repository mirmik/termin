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
    &quot;&quot;&quot;Renderer component that draws MeshDrawable with one or multiple passes.&quot;&quot;&quot;<br>
<br>
    inspect_fields = {<br>
        # mesh-инспект мы уже добавляли раньше<br>
        &quot;mesh&quot;: InspectField(<br>
            path=&quot;mesh&quot;,<br>
            label=&quot;Mesh&quot;,<br>
            kind=&quot;mesh&quot;,<br>
            # можно прямое присваивание, можно отдельный метод<br>
            setter=lambda obj, value: obj.update_mesh(value),<br>
        ),<br>
        &quot;material&quot;: InspectField(<br>
            path=&quot;material&quot;,<br>
            label=&quot;Material&quot;,<br>
            kind=&quot;material&quot;,<br>
            setter=lambda obj, value: obj.update_material(value),<br>
        ),<br>
    }<br>
<br>
    def __init__(<br>
        self,<br>
        mesh: MeshDrawable | None = None,<br>
        material: Material | None = None,<br>
        passes: list[RenderPass] | None = None,<br>
    ):<br>
        super().__init__(enabled=True)<br>
<br>
        if isinstance(mesh, Mesh3):<br>
            mesh = MeshDrawable(mesh)<br>
<br>
        self.mesh = mesh<br>
        self.material = material<br>
<br>
        self.passes: list[RenderPass] = []<br>
<br>
        if passes is not None:<br>
            # нормализация списка переданных проходов<br>
            for p in passes:<br>
                if isinstance(p, RenderPass):<br>
                    self.passes.append(p)<br>
                elif isinstance(p, Material):<br>
                    self.passes.append(RenderPass(material=p, state=RenderState()))<br>
                else:<br>
                    raise TypeError(&quot;passes must contain Material or RenderPass&quot;)<br>
        elif material is not None:<br>
            # если материал задан в конструкторе — как раньше: один проход<br>
            self.passes.append(RenderPass(material=material, state=RenderState()))<br>
<br>
    def update_mesh(self, mesh: MeshDrawable | None):<br>
        self.mesh = mesh<br>
<br>
    def update_material(self, material: Material | None):<br>
        &quot;&quot;&quot;<br>
        Вызывается инспектором при смене материала (и конструктором — косвенно).<br>
        Гарантируем, что если появился материал, будет хотя бы один RenderPass.<br>
        &quot;&quot;&quot;<br>
        self.material = material<br>
<br>
        if material is None:<br>
            # Можно:<br>
            #  - либо очищать материал у всех проходов,<br>
            #  - либо вообще ничего не делать (но draw тогда должен уметь жить с этим).<br>
            # Я бы для простоты просто обнулил материал в одиночном проходе.<br>
            if len(self.passes) == 1:<br>
                self.passes[0].material = None<br>
            return<br>
<br>
        if not self.passes:<br>
            # Новый компонент, до этого не было проходов —<br>
            # создаём дефолтный.<br>
            self.passes.append(RenderPass(material=material, state=RenderState()))<br>
        elif len(self.passes) == 1:<br>
            # старый режим: один проход → просто обновляем материал<br>
            self.passes[0].material = material<br>
        else:<br>
            # мультипасс — решай сам, как надо делать:<br>
            # можно менять только первый проход, можно все, можно вообще не трогать.<br>
            self.passes[0].material = material<br>
<br>
    # --- рендеринг ---<br>
<br>
    def required_shaders(self):<br>
        if self.material is None:<br>
            return<br>
        for p in self.passes:<br>
            yield p.material.shader<br>
<br>
    def draw(self, context: RenderContext):<br>
        if self.entity is None:<br>
            return<br>
<br>
        if self.mesh is None:<br>
            return<br>
<br>
        if self.material is None:<br>
            return<br>
<br>
        model = self.entity.model_matrix()<br>
        view = context.view<br>
        proj = context.projection<br>
        gfx = context.graphics<br>
        key = context.context_key<br>
<br>
        for p in self.passes:<br>
            gfx.apply_render_state(p.state)<br>
<br>
            mat = p.material<br>
            mat.apply(model, view, proj, graphics=gfx, context_key=key)<br>
<br>
            shader = mat.shader<br>
<br>
            if hasattr(context.scene, &quot;light_direction&quot;):<br>
                shader.set_uniform_vec3(&quot;u_light_dir&quot;, context.scene.light_direction)<br>
            if hasattr(context.scene, &quot;light_color&quot;):<br>
                shader.set_uniform_vec3(&quot;u_light_color&quot;, context.scene.light_color)<br>
<br>
            self.mesh.draw(context)<br>
<br>
        gfx.apply_render_state(RenderState())<br>
<!-- END SCAT CODE -->
</body>
</html>
