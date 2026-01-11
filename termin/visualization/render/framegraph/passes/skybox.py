from __future__ import annotations

from typing import Dict, List, Set, Tuple, TYPE_CHECKING

import numpy as np

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.framegraph.resource_spec import ResourceSpec
from termin.visualization.render.render_context import RenderContext
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.execute_context import ExecuteContext


class SkyBoxPass(RenderFramePass):
    """
    Render-проход, рисующий skybox-куб.

    Pass ожидает, что сцена предоставляет методы:
      - skybox_mesh() -> TcMesh
      - skybox_material() -> Material

    Проход выполняется с отключённой записью в depth-буфер, чтобы
    не мешать последующей геометрии.
    """

    category = "Render"

    node_inputs = [("input_res", "fbo")]
    node_outputs = [("output_res", "fbo")]
    node_inplace_pairs = [("input_res", "output_res")]

    inspect_fields = {
        "input_res": InspectField(path="input_res", label="Input Resource", kind="string"),
        "output_res": InspectField(path="output_res", label="Output Resource", kind="string"),
    }

    def __init__(
        self,
        input_res: str = "empty",
        output_res: str = "color",
        pass_name: str = "Skybox",
    ):
        super().__init__(pass_name=pass_name)
        self.input_res = input_res
        self.output_res = output_res

    def compute_reads(self) -> Set[str]:
        return {self.input_res}

    def compute_writes(self) -> Set[str]:
        return {self.output_res}

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        """SkyBoxPass читает input_res и пишет output_res inplace."""
        return [(self.input_res, self.output_res)]

    def get_resource_specs(self) -> list[ResourceSpec]:
        """
        Объявляет требования к входному ресурсу empty.

        Очистка: тёмно-серый цвет (0.2, 0.2, 0.2) + depth=1.0
        """
        return [
            ResourceSpec(
                resource=self.input_res,
                clear_color=(0.2, 0.2, 0.2, 1.0),
                clear_depth=1.0,
            )
        ]

    def execute(self, ctx: "ExecuteContext") -> None:
        """
        Рисует skybox до основной геометрии.

        Использует ту же формулу, что и обычный 3D-рендер:
            p_clip = P * V * M * p_local

        но:
          - M = I (единичная модельная матрица для куба вокруг камеры),
          - V берётся без трансляции, чтобы куб всегда оставался вокруг камеры
            при движении.
        """
        if ctx.scene is None:
            return

        mesh = ctx.scene.skybox_mesh()
        material = ctx.scene.skybox_material()

        if mesh is None or material is None:
            return

        _, _, width, height = ctx.rect

        fb = ctx.writes_fbos.get(self.output_res)
        if fb is None:
            return

        ctx.graphics.bind_framebuffer(fb)
        ctx.graphics.set_viewport(0, 0, width, height)

        # Матрицы камеры
        view = ctx.camera.view_matrix()
        projection = ctx.camera.projection_matrix()

        # Убираем трансляцию камеры — skybox не должен двигаться при перемещении
        view_no_translation = view.with_translation(0.0, 0.0, 0.0)

        # Модельная матрица — единичная, куб "вокруг камеры"
        from termin.geombase import Mat44
        model = Mat44.identity()

        # Skybox должен нарисоваться поверх содержимого color-буфера,
        # но не портить depth-буфер для последующей геометрии.
        ctx.graphics.set_depth_mask(False)
        ctx.graphics.set_depth_func("lequal")

        material.apply(
            model,
            view_no_translation,
            projection,
            graphics=ctx.graphics,
            context_key=ctx.context_key,
        )

        # Upload skybox colors based on type
        if ctx.scene.skybox_type == "solid":
            material.shader.set_uniform_vec3(
                "u_skybox_color",
                np.asarray(ctx.scene.skybox_color, dtype=np.float32),
            )
        elif ctx.scene.skybox_type == "gradient":
            material.shader.set_uniform_vec3(
                "u_skybox_top_color",
                np.asarray(ctx.scene.skybox_top_color, dtype=np.float32),
            )
            material.shader.set_uniform_vec3(
                "u_skybox_bottom_color",
                np.asarray(ctx.scene.skybox_bottom_color, dtype=np.float32),
            )

        render_context = RenderContext(
            view=view_no_translation,
            projection=projection,
            camera=ctx.camera,
            scene=ctx.scene,
            context_key=ctx.context_key,
            graphics=ctx.graphics,
            phase="skybox",
        )

        # Draw skybox mesh
        if mesh.is_valid:
            gpu = ctx.scene.skybox_gpu()
            gpu.draw(render_context, mesh.mesh, mesh.version)

        # Возвращаем стандартные настройки глубины
        ctx.graphics.set_depth_func("less")
        ctx.graphics.set_depth_mask(True)
