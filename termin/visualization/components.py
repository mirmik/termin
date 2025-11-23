"""Common component implementations (renderers, etc.)."""

from __future__ import annotations

from typing import Iterable

import numpy as np

from .entity import Component, RenderContext
from .material import Material
from .mesh import MeshDrawable

from termin.geombase.pose3 import Pose3
from termin.visualization.renderpass import RenderState, RenderPass


# termin/visualization/components.py

from termin.visualization.renderpass import RenderPass, RenderState

class MeshRenderer(Component):
    """Renderer component that draws MeshDrawable with one or multiple passes."""

    def __init__(self, mesh: MeshDrawable, material: Material, passes=None):
        super().__init__(enabled=True)
        self.mesh = mesh
        self.material = material

        if passes is None:
            # старый режим: один материал -> один проход
            self.passes: list[RenderPass] = [
                RenderPass(material=material, state=RenderState())
            ]
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

    def required_shaders(self):
        for p in self.passes:
            yield p.material.shader

    def draw(self, context: RenderContext):
        if self.entity is None:
            return

        model = self.entity.model_matrix()
        view  = context.view
        proj  = context.projection
        gfx   = context.graphics
        key   = context.context_key

        for p in self.passes:
            # Применяем полное состояние прохода
            gfx.apply_render_state(p.state)

            mat = p.material
            mat.apply(model, view, proj, graphics=gfx, context_key=key)

            shader = mat.shader

            if hasattr(context.scene, "light_direction"):
                shader.set_uniform_vec3("u_light_dir", context.scene.light_direction)
            if hasattr(context.scene, "light_color"):
                shader.set_uniform_vec3("u_light_color", context.scene.light_color)

            # cam_entity = context.camera.entity if context.camera else None
            # if cam_entity is not None:
            #     shader.set_uniform_vec3(
            #         "u_view_pos",
            #         cam_entity.transform.global_pose().lin
            #     )

            self.mesh.draw(context)

        # после меша возвращаемся к "нормальному" дефолтному состоянию
        gfx.apply_render_state(RenderState())



class SkyboxRenderer(MeshRenderer):
    """Specialized renderer for skyboxes (no depth writes and view without translation)."""

    def draw(self, context: RenderContext):
        if self.entity is None:
            return
        camera_entity = context.camera.entity if context.camera is not None else None
        if camera_entity is not None:
            #self.entity.transform.local_pose.lin = camera_entity.transform.global_pose().lin.copy()
            self.entity.transform.relocate(Pose3(lin = camera_entity.transform.global_pose().lin))
        original_view = context.view
        view_no_translation = np.array(original_view, copy=True)
        view_no_translation[:3, 3] = 0.0
        context.graphics.set_depth_mask(False)
        context.graphics.set_depth_func("lequal")
        self.material.apply(self.entity.model_matrix(), view_no_translation, context.projection, graphics=context.graphics, context_key=context.context_key)
        self.mesh.draw(context)
        context.graphics.set_depth_func("less")
        context.graphics.set_depth_mask(True)
