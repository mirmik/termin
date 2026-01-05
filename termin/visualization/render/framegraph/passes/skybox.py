from __future__ import annotations

from typing import Dict, List, Set, Tuple

import numpy as np

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.framegraph.resource_spec import ResourceSpec
from termin.visualization.render.render_context import RenderContext
from termin.editor.inspect_field import InspectField


class SkyBoxPass(RenderFramePass):
    """
    Render-проход, рисующий skybox-куб.

    Pass ожидает, что сцена предоставляет методы:
      - skybox_mesh() -> TcMesh
      - skybox_material() -> Material

    Проход выполняется с отключённой записью в depth-буфер, чтобы
    не мешать последующей геометрии.
    """

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

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: Dict[str, "FramebufferHandle | None"],
        writes_fbos: Dict[str, "FramebufferHandle | None"],
        rect: tuple[int, int, int, int],
        scene,
        camera,
        context_key: int,
        lights=None,
        canvas=None,
    ):
        """
        Рисует skybox до основной геометрии.

        Использует ту же формулу, что и обычный 3D-рендер:
            p_clip = P * V * M * p_local

        но:
          - M = I (единичная модельная матрица для куба вокруг камеры),
          - V берётся без трансляции, чтобы куб всегда оставался вокруг камеры
            при движении.
        """
        if scene is None:
            return

        mesh = scene.skybox_mesh()
        material = scene.skybox_material()
        
        if mesh is None or material is None:
            return

        _, _, width, height = rect

        fb = writes_fbos.get(self.output_res)
        if fb is None:
            return

        graphics.bind_framebuffer(fb)
        graphics.set_viewport(0, 0, width, height)

        # Матрицы камеры
        view = camera.view_matrix()
        projection = camera.projection_matrix()

        # Убираем трансляцию камеры — skybox не должен двигаться при перемещении
        view_no_translation = np.array(view, copy=True)
        view_no_translation[:3, 3] = 0.0

        # Модельная матрица — единичная, куб "вокруг камеры"
        model = np.identity(4, dtype=np.float32)

        # Skybox должен нарисоваться поверх содержимого color-буфера,
        # но не портить depth-буфер для последующей геометрии.
        graphics.set_depth_mask(False)
        graphics.set_depth_func("lequal")

        material.apply(
            model,
            view_no_translation,
            projection,
            graphics=graphics,
            context_key=context_key,
        )

        # Upload skybox colors based on type
        if scene.skybox_type == "solid":
            material.shader.set_uniform_vec3(
                "u_skybox_color",
                np.asarray(scene.skybox_color, dtype=np.float32),
            )
        elif scene.skybox_type == "gradient":
            material.shader.set_uniform_vec3(
                "u_skybox_top_color",
                np.asarray(scene.skybox_top_color, dtype=np.float32),
            )
            material.shader.set_uniform_vec3(
                "u_skybox_bottom_color",
                np.asarray(scene.skybox_bottom_color, dtype=np.float32),
            )

        render_context = RenderContext(
            view=view_no_translation,
            projection=projection,
            camera=camera,
            scene=scene,
            context_key=context_key,
            graphics=graphics,
            phase="skybox",
        )

        # Draw skybox mesh
        if mesh.is_valid:
            gpu = scene.skybox_gpu()
            gpu.draw(render_context, mesh.mesh, mesh.version)

        # Возвращаем стандартные настройки глубины
        graphics.set_depth_func("less")
        graphics.set_depth_mask(True)
