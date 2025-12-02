from __future__ import annotations

from typing import List

from termin.visualization.render.framegraph.context import FrameContext
from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.components import MeshRenderer
from termin.visualization.core.entity import RenderContext
from termin.visualization.render.renderpass import RenderState
from termin.visualization.render.framegraph.passes.present import blit_fbo_to_fbo
from termin.visualization.render.materials.depth_material import DepthMaterial


class DepthPass(RenderFramePass):
    """
    Проход рендеринга, который пишет линейную глубину сцены
    в отдельный ресурс (обычно "depth").

    По структуре очень похож на IdPass: сам создаёт FBO,
    обходит сущности с MeshRenderer и рисует их с материалом DepthMaterial.
    """

    def __init__(
        self,
        input_res: str = "empty_depth",
        output_res: str = "depth",
        pass_name: str = "Depth",
    ):
        super().__init__(
            pass_name=pass_name,
            reads={input_res},
            writes={output_res},
            inplace=True,
        )
        self.input_res = input_res
        self.output_res = output_res

        # Кэш имён сущностей с MeshRenderer (для внутренних точек дебага)
        self._entity_names: List[str] = []

        self._material: DepthMaterial | None = None

    def _get_material(self) -> DepthMaterial:
        if self._material is None:
            self._material = DepthMaterial()
        return self._material

    def get_internal_symbols(self) -> List[str]:
        """
        Список имён сущностей, для которых можно запросить
        промежуточное состояние depth-карты через дебаггер.
        """
        return list(self._entity_names)

    def execute(self, ctx: FrameContext):
        gfx = ctx.graphics
        window = ctx.window
        viewport = ctx.viewport
        scene = viewport.scene
        camera = viewport.camera
        px, py, pw, ph = ctx.rect
        key = ctx.context_key

        # FBO для depth-ресурса создаём/берём так же, как ColorPass
        fb = window.get_viewport_fbo(viewport, self.output_res, (pw, ph))
        ctx.fbos[self.output_res] = fb

        # Настройка debug-вывода (как в ColorPass/IdPass)
        debug_symbol, debug_output = self.get_debug_internal_point()
        debug_fb = None
        if debug_symbol is not None and debug_output is not None:
            debug_fb = window.get_viewport_fbo(viewport, debug_output, (pw, ph))
            ctx.fbos[debug_output] = debug_fb

        # Обновляем список имён
        self._entity_names = []

        gfx.bind_framebuffer(fb)
        gfx.set_viewport(0, 0, pw, ph)
        # Чистим: белый цвет (максимальная глубина), глубина = 1
        gfx.clear_color_depth((1.0, 1.0, 1.0, 1.0))

        # Матрицы камеры
        view = camera.view_matrix()
        proj = camera.projection_matrix()

        # Контекст рендеринга
        render_ctx = RenderContext(
            view=view,
            projection=proj,
            graphics=gfx,
            context_key=key,
            scene=scene,
            camera=camera,
            renderer=window.renderer,
            phase="depth",
        )

        depth_material = self._get_material()

        # Аккуратно получаем near/far без getattr
        try:
            near_plane = float(camera.near)
        except AttributeError:
            near_plane = 0.1

        try:
            far_plane = float(camera.far)
        except AttributeError:
            far_plane = 100.0

        depth_material.update_camera_planes(near_plane, far_plane)

        # Состояние рендера для depth-прохода
        gfx.apply_render_state(
            RenderState(
                depth_test=True,
                depth_write=True,
                blend=False,
                cull=True,
            )
        )

        # Обход сущностей и рисование глубины
        for ent in scene.entities:
            mr = ent.get_component(MeshRenderer)
            if mr is None:
                continue

            self._entity_names.append(ent.name)

            model = ent.model_matrix()
            depth_material.apply(model, view, proj, graphics=gfx, context_key=key)

            if mr.mesh is not None:
                mr.mesh.draw(render_ctx)

            if debug_fb is not None and ent.name == debug_symbol:
                self._blit_to_debug(gfx, fb, debug_fb, (pw, ph), key)

    def _blit_to_debug(
        self,
        gfx,
        src_fb,
        dst_fb,
        size,
        context_key: int,
    ) -> None:
        """
        Копирует depth-FBO в debug-FBO и возвращает привязку исходного.
        """
        blit_fbo_to_fbo(gfx, src_fb, dst_fb, size, context_key)
        gfx.bind_framebuffer(src_fb)
        gfx.set_viewport(0, 0, size[0], size[1])
