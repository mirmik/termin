from __future__ import annotations

from typing import List, Optional

from termin.visualization.render.framegraph.context import FrameContext
from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.shader import ShaderProgram

GIZMO_MASK_VERT = """
#version 330 core
layout(location = 0) in vec3 a_position;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

void main() {
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""

GIZMO_MASK_FRAG = """
#version 330 core
out vec4 fragColor;
uniform vec4 u_color;

void main() {
    // RGB нам не важен, только альфа
    fragColor = vec4(0.0, 0.0, 0.0, u_color.a);
}
"""


class GizmoPass(RenderFramePass):
    def __init__(self, input_res: str = "id", output_res: str = "id", pass_name: str = "GizmoPass",
                 gizmo_entities: Optional[List["Entity"]] = None):
        super().__init__(
            pass_name=pass_name,
            reads={input_res},
            writes={output_res},
            inplace=True,
        )
        if gizmo_entities is None:
            gizmo_entities = []
        self._gizmo_entities = gizmo_entities
        self.input_res = input_res
        self.output_res = output_res
        self._shader: ShaderProgram | None = None

    def _ensure_shader(self, gfx) -> ShaderProgram:
        if self._shader is None:
            self._shader = ShaderProgram(GIZMO_MASK_VERT, GIZMO_MASK_FRAG)
            self._shader.ensure_ready(gfx)
        return self._shader

    def execute(self, ctx: FrameContext):
        gfx = ctx.graphics
        window = ctx.window
        viewport = ctx.viewport
        camera = viewport.camera
        px, py, pw, ph = ctx.rect
        key = ctx.context_key

        fb = ctx.fbos.get(self.output_res)
        gfx.bind_framebuffer(fb)
        gfx.set_viewport(0, 0, pw, ph)

        # глубину тестируем, но не пишем
        gfx.set_depth_test(True)
        gfx.set_depth_mask(False)

        # главное отличие: пишем только в альфу
        gfx.set_color_mask(False, False, False, True)

        view = camera.get_view_matrix()
        proj = camera.get_projection_matrix()

        shader = self._ensure_shader(gfx)
        shader.ensure_ready(gfx)
        shader.use()
        shader.set_uniform_matrix4("u_view", view)
        shader.set_uniform_matrix4("u_projection", proj)

        from termin.visualization.core.entity import RenderContext
        ctx_render = RenderContext(
            view=view,
            projection=proj,
            camera=camera,
            scene=viewport.scene,
            renderer=window.renderer,
            context_key=key,
            graphics=gfx,
            phase="gizmo_mask",
        )

        from termin.visualization.render.components import MeshRenderer

        index = 1
        maxindex = len(self._gizmo_entities)

        for ent in self._gizmo_entities:
            if not ent.active or not ent.visible:
                continue
            mr = ent.get_component(MeshRenderer)
            if mr is None or mr.mesh is None:
                continue

            alpha = index * 1.0 / maxindex
            shader.set_uniform_vec4("u_color", (0.0, 0.0, 0.0, alpha))
            model = ent.model_matrix()
            shader.set_uniform_matrix4("u_model", model)
            mr.mesh.draw(ctx_render)
            index += 1

        # возвращаем нормальную маску цвета и запись глубины
        gfx.set_color_mask(True, True, True, True)
        gfx.set_depth_mask(True)
