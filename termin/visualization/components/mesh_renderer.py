from __future__ import annotations

from typing import Iterable, Optional

import numpy as np

from ..entity import Component, RenderContext
from ..material import Material
from ..mesh import MeshDrawable
from termin.mesh.mesh import Mesh3

from termin.geombase.pose3 import Pose3
from termin.visualization.renderpass import RenderState, RenderPass

from termin.visualization.inspect import InspectField


class MeshRenderer(Component):
    """Renderer component that draws MeshDrawable with one or multiple passes."""

    inspect_fields = {
        "mesh": InspectField(
            path="mesh",
            label="Mesh",
            kind="mesh",  # ресурс типа MeshDrawable
            # setter=lambda obj, value: obj.update_mesh(value),
        ),
        "material": InspectField(
            path="material",
            label="Material",
            kind="material",  # ресурс типа Material
            setter=lambda obj, value: obj.update_material(value),
        ),
    }

    def __init__(
        self,
        mesh: MeshDrawable | Mesh3 | None = None,
        material: Material | None = None,
        passes=None,
    ):
        super().__init__(enabled=True)

        # допускаем голый Mesh3 для удобства, но внутри всегда MeshDrawable
        if isinstance(mesh, Mesh3):
            mesh = MeshDrawable(mesh)

        self.mesh: Optional[MeshDrawable] = mesh
        self.material = material

        if passes is None:
            self.passes: list[RenderPass] = (
                [RenderPass(material=material, state=RenderState())]
                if material is not None
                else []
            )
        else:
            normalized: list[RenderPass] = []
            for p in passes:
                if isinstance(p, RenderPass):
                    normalized.append(p)
                elif isinstance(p, Material):
                    normalized.append(RenderPass(material=p, state=RenderState()))
                else:
                    raise TypeError("passes must contain Material or RenderPass")
            self.passes = normalized

    # --- инспекторные апдейты ---

    # def update_mesh(self, mesh: MeshDrawable | None):
    #     self.mesh = mesh

    def update_material(self, material: Material | None):
        self.material = material
        if len(self.passes) == 1:
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

            if hasattr(context.scene, "light_direction"):
                shader.set_uniform_vec3("u_light_dir", context.scene.light_direction)
            if hasattr(context.scene, "light_color"):
                shader.set_uniform_vec3("u_light_color", context.scene.light_color)

            self.mesh.draw(context)

        gfx.apply_render_state(RenderState())
