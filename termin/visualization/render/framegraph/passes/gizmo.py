from __future__ import annotations

from typing import List, Optional, Set, Tuple

from typing import TYPE_CHECKING

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.shader import ShaderProgram
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.execute_context import ExecuteContext

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


from typing import Callable

class GizmoPass(RenderFramePass):
    category = "ID/Picking"

    node_inputs = [("input_res", "fbo")]
    node_outputs = [("output_res", "fbo")]
    node_inplace_pairs = [("input_res", "output_res")]

    inspect_fields = {
        "input_res": InspectField(path="input_res", label="Input Resource", kind="string"),
        "output_res": InspectField(path="output_res", label="Output Resource", kind="string"),
    }

    def __init__(self, input_res: str = "id", output_res: str = "id", pass_name: str = "GizmoPass",
                 gizmo_entities: Optional[List["Entity"] | Callable[[], List["Entity"]]] = None):
        super().__init__(pass_name=pass_name)
        # gizmo_entities может быть списком или callable, возвращающим список
        self._gizmo_entities_source = gizmo_entities
        self.input_res = input_res
        self.output_res = output_res
        self._shader: ShaderProgram | None = None

    def compute_reads(self) -> Set[str]:
        return {self.input_res}

    def compute_writes(self) -> Set[str]:
        return {self.output_res}

    def _get_gizmo_entities(self) -> List["Entity"]:
        """Возвращает актуальный список gizmo entities."""
        if self._gizmo_entities_source is None:
            return []
        if callable(self._gizmo_entities_source):
            return self._gizmo_entities_source()
        return self._gizmo_entities_source

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        """GizmoPass читает input_res и пишет output_res inplace."""
        return [(self.input_res, self.output_res)]

    def _ensure_shader(self, gfx, context_key: int = 0) -> ShaderProgram:
        if self._shader is None:
            self._shader = ShaderProgram(GIZMO_MASK_VERT, GIZMO_MASK_FRAG)
        self._shader.ensure_ready(gfx, context_key)
        return self._shader

    def execute(self, ctx: "ExecuteContext") -> None:
        px, py, pw, ph = ctx.rect
        key = ctx.context_key

        fb = ctx.writes_fbos.get(self.output_res)
        ctx.graphics.bind_framebuffer(fb)
        ctx.graphics.set_viewport(0, 0, pw, ph)

        # очищаем depth чтобы гизмо был кликабелен поверх сцены
        ctx.graphics.clear_depth()

        # глубину тестируем, но не пишем
        ctx.graphics.set_depth_test(True)
        ctx.graphics.set_depth_mask(False)

        # главное отличие: пишем только в альфу
        ctx.graphics.set_color_mask(False, False, False, True)

        view = ctx.camera.get_view_matrix()
        proj = ctx.camera.get_projection_matrix()

        shader = self._ensure_shader(ctx.graphics, key)
        shader.use()
        shader.set_uniform_matrix4("u_view", view)
        shader.set_uniform_matrix4("u_projection", proj)

        from termin.visualization.render.render_context import RenderContext
        ctx_render = RenderContext(
            view=view,
            projection=proj,
            camera=ctx.camera,
            scene=ctx.scene,
            context_key=key,
            graphics=ctx.graphics,
            phase="gizmo_mask",
        )

        from termin.visualization.render.components import MeshRenderer

        gizmo_entities = self._get_gizmo_entities()
        index = 1
        maxindex = len(gizmo_entities)

        for ent in gizmo_entities:
            if not ent.active or not ent.visible:
                continue
            mr = ent.get_component(MeshRenderer)
            if mr is None or mr.mesh is None:
                continue

            # alpha < 1.0 для гизмо, alpha=1.0 зарезервирована для обычных объектов
            alpha = index * 1.0 / (maxindex + 1)
            shader.set_uniform_vec4("u_color", (0.0, 0.0, 0.0, alpha))
            model = ent.model_matrix()
            shader.set_uniform_matrix4("u_model", model)
            tc_mesh = mr.mesh
            if tc_mesh is not None and tc_mesh.is_valid:
                gpu = mr.mesh_gpu
                gpu.draw(ctx_render, tc_mesh.mesh, tc_mesh.version)
            index += 1

        # возвращаем нормальное состояние
        ctx.graphics.set_color_mask(True, True, True, True)
        ctx.graphics.set_depth_mask(True)
        ctx.graphics.set_cull_face(True)
