from __future__ import annotations

from typing import Dict, List, Set, Tuple, TYPE_CHECKING

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.framegraph.resource_spec import ResourceSpec
from termin.visualization.render.render_context import RenderContext
from termin.editor.inspect_field import InspectField
from termin.geombase import Vec3

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

        # Check skybox type - skip if "none"
        skybox_type = ctx.scene.skybox_type
        if skybox_type == "none":
            return

        # Convert skybox_type string to int for ensure_skybox_material
        # TC_SKYBOX_NONE=0, TC_SKYBOX_GRADIENT=1, TC_SKYBOX_SOLID=2
        type_int = {"none": 0, "gradient": 1, "solid": 2}.get(skybox_type, 1)

        mesh = ctx.scene.skybox_mesh()
        # Ensure material exists for current skybox type
        material = ctx.scene.ensure_skybox_material(type_int)

        # Check validity - TcMesh/TcMaterial from TcSceneRef may be invalid
        if mesh is None or not mesh.is_valid:
            return
        if material is None or not material.is_valid:
            return

        _, _, width, height = ctx.rect

        fb = ctx.writes_fbos.get(self.output_res)
        if fb is None:
            return

        # Check type - skip if not a FramebufferHandle
        from termin.graphics import FramebufferHandle
        if not isinstance(fb, FramebufferHandle):
            from termin._native import log
            log.warn(f"[SkyboxPass] output '{self.output_res}' is {type(fb).__name__}, not FramebufferHandle")
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

        # Set skybox colors on material before applying
        if skybox_type == "solid":
            c = ctx.scene.skybox_color
            material.set_uniform_vec3("u_skybox_color", Vec3(c[0], c[1], c[2]))
        elif skybox_type == "gradient":
            top = ctx.scene.skybox_top_color
            bottom = ctx.scene.skybox_bottom_color
            material.set_uniform_vec3("u_skybox_top_color", Vec3(top[0], top[1], top[2]))
            material.set_uniform_vec3("u_skybox_bottom_color", Vec3(bottom[0], bottom[1], bottom[2]))

        # Apply material with MVP matrices
        material.apply(model, view_no_translation, projection)

        render_context = RenderContext(
            view=view_no_translation,
            projection=projection,
            camera=ctx.camera,
            scene=ctx.scene,
            graphics=ctx.graphics,
            phase="skybox",
        )

        # Draw skybox mesh
        if mesh.is_valid:
            mesh.draw_gpu()

        # Возвращаем стандартные настройки глубины
        ctx.graphics.set_depth_func("less")
        ctx.graphics.set_depth_mask(True)
