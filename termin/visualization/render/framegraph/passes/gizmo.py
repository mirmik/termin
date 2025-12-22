from __future__ import annotations

from typing import List, Optional, Tuple

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


from typing import Callable

class GizmoPass(RenderFramePass):
    def __init__(self, input_res: str = "id", output_res: str = "id", pass_name: str = "GizmoPass",
                 gizmo_entities: Optional[List["Entity"] | Callable[[], List["Entity"]]] = None):
        super().__init__(
            pass_name=pass_name,
            reads={input_res},
            writes={output_res},
        )
        # gizmo_entities может быть списком или callable, возвращающим список
        self._gizmo_entities_source = gizmo_entities
        self.input_res = input_res
        self.output_res = output_res
        self._shader: ShaderProgram | None = None

    def _serialize_params(self) -> dict:
        """Сериализует параметры GizmoPass."""
        return {
            "input_res": self.input_res,
            "output_res": self.output_res,
        }

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "GizmoPass":
        """Создаёт GizmoPass из сериализованных данных."""
        return cls(
            input_res=data.get("input_res", "id"),
            output_res=data.get("output_res", "id"),
            pass_name=data.get("pass_name", "GizmoPass"),
            gizmo_entities=None,  # Runtime, не сериализуется
        )

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

    def _ensure_shader(self, gfx) -> ShaderProgram:
        if self._shader is None:
            self._shader = ShaderProgram(GIZMO_MASK_VERT, GIZMO_MASK_FRAG)
            self._shader.ensure_ready(gfx)
        return self._shader

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict[str, "FramebufferHandle" | None],
        writes_fbos: dict[str, "FramebufferHandle" | None],
        rect: tuple[int, int, int, int],
        scene,
        camera,
        context_key: int,
        lights=None,
        canvas=None,
    ):
        px, py, pw, ph = rect
        key = context_key

        fb = writes_fbos.get(self.output_res)
        graphics.bind_framebuffer(fb)
        graphics.set_viewport(0, 0, pw, ph)

        # очищаем depth чтобы гизмо был кликабелен поверх сцены
        graphics.clear_depth()

        # глубину тестируем, но не пишем
        graphics.set_depth_test(True)
        graphics.set_depth_mask(False)

        # главное отличие: пишем только в альфу
        graphics.set_color_mask(False, False, False, True)

        view = camera.get_view_matrix()
        proj = camera.get_projection_matrix()

        shader = self._ensure_shader(graphics)
        shader.ensure_ready(graphics)
        shader.use()
        shader.set_uniform_matrix4("u_view", view)
        shader.set_uniform_matrix4("u_projection", proj)

        from termin.visualization.render.render_context import RenderContext
        ctx_render = RenderContext(
            view=view,
            projection=proj,
            camera=camera,
            scene=scene,
            context_key=key,
            graphics=graphics,
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
            mesh_handle = mr.mesh
            if mesh_handle is not None:
                mesh_data = mesh_handle.mesh
                gpu = mesh_handle.gpu
                if mesh_data is not None and gpu is not None:
                    gpu.draw(ctx_render, mesh_data, mesh_handle.version)
            index += 1

        # возвращаем нормальное состояние
        graphics.set_color_mask(True, True, True, True)
        graphics.set_depth_mask(True)
        graphics.set_cull_face(True)
