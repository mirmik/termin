from __future__ import annotations

from typing import List, Optional, Set, Tuple

from typing import TYPE_CHECKING

from tgfx import TcShader
from termin.visualization.render.framegraph.passes.base import RenderFramePass
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
        self._shader: TcShader | None = None

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

    def _ensure_shader(self) -> TcShader:
        if self._shader is None:
            self._shader = TcShader.from_sources(GIZMO_MASK_VERT, GIZMO_MASK_FRAG, "", "GizmoMask")
        # tgfx2 path compiles lazily via tc_shader_ensure_tgfx2 in execute().
        return self._shader

    def execute(self, ctx: "ExecuteContext") -> None:
        px, py, pw, ph = ctx.rect

        if ctx.ctx2 is None:
            from tcbase import log
            log.error(f"[GizmoPass] '{self.pass_name}': ctx.ctx2 is None — GizmoPass is tgfx2-only")
            return

        from tgfx._tgfx_native import (
            tc_shader_ensure_tgfx2,
            wrap_fbo_color_as_tgfx2,
            draw_tc_mesh,
            CULL_NONE,
            PIXEL_RGBA8,
        )

        ctx2 = ctx.ctx2
        fb = ctx.writes_fbos.get(self.output_res)
        if fb is None:
            return

        target_tex2 = wrap_fbo_color_as_tgfx2(ctx2, fb)
        if not target_tex2:
            return

        view = ctx.camera.get_view_matrix()
        proj = ctx.camera.get_projection_matrix()

        shader = self._ensure_shader()
        pair = tc_shader_ensure_tgfx2(ctx2, shader)
        if not pair.vs or not pair.fs:
            return

        ctx2.begin_pass(target_tex2, clear_depth_enabled=True, clear_depth=1.0)
        ctx2.set_viewport(0, 0, pw, ph)
        ctx2.set_depth_test(True)
        ctx2.set_depth_write(False)
        ctx2.set_blend(False)
        ctx2.set_cull(CULL_NONE)
        ctx2.set_color_format(PIXEL_RGBA8)
        # Пишем только в альфу (id gizmo'а)
        ctx2.set_color_mask(False, False, False, True)
        ctx2.bind_shader(pair.vs, pair.fs)

        ctx2.set_uniform_mat4("u_view", list(view.data), False)
        ctx2.set_uniform_mat4("u_projection", list(proj.data), False)

        from termin.render_components import MeshRenderer

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
            ctx2.set_uniform_vec4("u_color", 0.0, 0.0, 0.0, alpha)
            model = ent.model_matrix()
            ctx2.set_uniform_mat4("u_model", list(model.data), False)

            tc_mesh = mr.mesh
            if tc_mesh is not None and tc_mesh.is_valid:
                draw_tc_mesh(ctx2, tc_mesh)
            index += 1

        ctx2.end_pass()
        # Восстанавливаем нормальную color mask для последующих пассов.
        # begin_pass следующего пасса всё равно перезапишет state, но
        # внутри ctx2 pipeline cache значение пойдёт в новую запись.
        ctx2.set_color_mask(True, True, True, True)
