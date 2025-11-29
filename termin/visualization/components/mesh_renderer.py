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
    """Renderer component that draws MeshDrawable with one or multiple passes."""

    inspect_fields = {
        # mesh-инспект мы уже добавляли раньше
        "mesh": InspectField(
            path="mesh",
            label="Mesh",
            kind="mesh",
            # можно прямое присваивание, можно отдельный метод
            setter=lambda obj, value: obj.update_mesh(value),
        ),
        "material": InspectField(
            path="material",
            label="Material",
            kind="material",
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

        if material is None and passes is None:
            material = Material()

        self.mesh = mesh
        if passes is None:
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
                    raise TypeError("passes must contain Material or RenderPass")
        elif material is not None:
            # если материал задан в конструкторе — как раньше: один проход
            self.passes.append(RenderPass(material=material, state=RenderState()))

    def update_mesh(self, mesh: MeshDrawable | None):
        self.mesh = mesh

    def update_material(self, material: Material | None):
        """
        Вызывается инспектором при смене материала (и конструктором — косвенно).
        Гарантируем, что если появился материал, будет хотя бы один RenderPass.
        """
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
        for p in self.passes:
            yield p.material.shader

    def draw(self, context: RenderContext):
        if self.entity is None:
            return

        if self.mesh is None:
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

            if hasattr(context.scene, "light_direction"):
                shader.set_uniform_vec3("u_light_dir", context.scene.light_direction)
            if hasattr(context.scene, "light_color"):
                shader.set_uniform_vec3("u_light_color", context.scene.light_color)

            self.mesh.draw(context)

        gfx.apply_render_state(RenderState())
