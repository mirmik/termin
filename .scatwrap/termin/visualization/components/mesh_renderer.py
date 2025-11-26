<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/components/mesh_renderer.py</title>
</head>
<body>
<pre><code>
from __future__ import annotations

from typing import Iterable, Optional

import numpy as np

from ..entity import Component, RenderContext
from ..mesh import MeshDrawable
from termin.mesh.mesh import Mesh3
from termin.geombase.pose3 import Pose3
from termin.visualization.renderpass import RenderState, RenderPass
from termin.visualization.inspect import InspectField
from termin.visualization.material import Material

class MeshRenderer(Component):
    &quot;&quot;&quot;Renderer component that draws MeshDrawable with one or multiple passes.&quot;&quot;&quot;

    inspect_fields = {
        # mesh-инспект мы уже добавляли раньше
        &quot;mesh&quot;: InspectField(
            path=&quot;mesh&quot;,
            label=&quot;Mesh&quot;,
            kind=&quot;mesh&quot;,
            # можно прямое присваивание, можно отдельный метод
            setter=lambda obj, value: obj.update_mesh(value),
        ),
        &quot;material&quot;: InspectField(
            path=&quot;material&quot;,
            label=&quot;Material&quot;,
            kind=&quot;material&quot;,
            setter=lambda obj, value: obj.update_material(value),
        ),
    }

    def __init__(
        self,
        mesh: MeshDrawable | None = None,
        material: Material | None = None,
        passes: list[RenderPass] | None = None,
    ):
        super().__init__(enabled=True)

        if isinstance(mesh, Mesh3):
            mesh = MeshDrawable(mesh)

        self.mesh = mesh
        self.material = material

        self.passes: list[RenderPass] = []

        if passes is not None:
            # нормализация списка переданных проходов
            for p in passes:
                if isinstance(p, RenderPass):
                    self.passes.append(p)
                elif isinstance(p, Material):
                    self.passes.append(RenderPass(material=p, state=RenderState()))
                else:
                    raise TypeError(&quot;passes must contain Material or RenderPass&quot;)
        elif material is not None:
            # если материал задан в конструкторе — как раньше: один проход
            self.passes.append(RenderPass(material=material, state=RenderState()))

    def update_mesh(self, mesh: MeshDrawable | None):
        self.mesh = mesh

    def update_material(self, material: Material | None):
        &quot;&quot;&quot;
        Вызывается инспектором при смене материала (и конструктором — косвенно).
        Гарантируем, что если появился материал, будет хотя бы один RenderPass.
        &quot;&quot;&quot;
        self.material = material

        if material is None:
            # Можно:
            #  - либо очищать материал у всех проходов,
            #  - либо вообще ничего не делать (но draw тогда должен уметь жить с этим).
            # Я бы для простоты просто обнулил материал в одиночном проходе.
            if len(self.passes) == 1:
                self.passes[0].material = None
            return

        if not self.passes:
            # Новый компонент, до этого не было проходов —
            # создаём дефолтный.
            self.passes.append(RenderPass(material=material, state=RenderState()))
        elif len(self.passes) == 1:
            # старый режим: один проход → просто обновляем материал
            self.passes[0].material = material
        else:
            # мультипасс — решай сам, как надо делать:
            # можно менять только первый проход, можно все, можно вообще не трогать.
            self.passes[0].material = material

    # --- рендеринг ---

    def required_shaders(self):
        if self.material is None:
            return
        for p in self.passes:
            yield p.material.shader

    def draw(self, context: RenderContext):
        if self.entity is None:
            return

        if self.mesh is None:
            return

        if self.material is None:
            return

        model = self.entity.model_matrix()
        view = context.view
        proj = context.projection
        gfx = context.graphics
        key = context.context_key

        for p in self.passes:
            gfx.apply_render_state(p.state)

            mat = p.material
            mat.apply(model, view, proj, graphics=gfx, context_key=key)

            shader = mat.shader

            if hasattr(context.scene, &quot;light_direction&quot;):
                shader.set_uniform_vec3(&quot;u_light_dir&quot;, context.scene.light_direction)
            if hasattr(context.scene, &quot;light_color&quot;):
                shader.set_uniform_vec3(&quot;u_light_color&quot;, context.scene.light_color)

            self.mesh.draw(context)

        gfx.apply_render_state(RenderState())

</code></pre>
</body>
</html>
