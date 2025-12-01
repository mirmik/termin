from __future__ import annotations

from typing import List

from termin.visualization.render.framegraph.context import FrameContext
from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.components import MeshRenderer
from termin.visualization.core.picking import id_to_rgb
from termin.visualization.core.entity import RenderContext
from termin.visualization.render.renderpass import RenderState
from termin.visualization.render.framegraph.passes.present import blit_fbo_to_fbo


class IdPass(RenderFramePass):
    def __init__(
        self,
        input_res: str = "empty",
        output_res: str = "id",
        pass_name: str = "IdPass",
    ):
        super().__init__(
            pass_name=pass_name,
            reads={input_res},
            writes={output_res},
            inplace=True,
        )
        self.input_res = input_res
        self.output_res = output_res

        # Кэш имён отрисовываемых pickable-энтити.
        self._entity_names: List[str] = []

    def get_internal_symbols(self) -> List[str]:
        """
        Список имён pickable-сущностей сцены.

        Используется дебаггером для выбора промежуточного состояния
        после прорисовки конкретной сущности в ID-карту.
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

        fb = ctx.fbos.get(self.output_res)
        if fb is None:
            return

        # Внутренняя точка дебага (символ и целевой ресурс)
        debug_symbol, debug_output = self.get_debug_internal_point()
        debug_fb = None
        if debug_symbol is not None and debug_output is not None:
            debug_fb = window.get_viewport_fbo(viewport, debug_output, (pw, ph))
            ctx.fbos[debug_output] = debug_fb

        # Обновляем список имён pickable-сущностей
        self._entity_names = []

        gfx.bind_framebuffer(fb)
        gfx.set_viewport(0, 0, pw, ph)
        gfx.clear_color_depth((0.0, 0.0, 0.0, 0.0))

        # Карта сущность -> числовой id (цвет кодируем через id_to_rgb)
        pick_ids: dict = {}
        for ent in scene.entities:
            if not ent.is_pickable():
                continue
            mr = ent.get_component(MeshRenderer)
            if mr is None:
                continue
            pid = window._get_pick_id_for_entity(ent)
            pick_ids[ent] = pid
            self._entity_names.append(ent.name)

        # Матрицы камеры для фазовой формулы p_clip = P · V · M · p_local
        view = camera.view_matrix()
        proj = camera.projection_matrix()

        render_ctx = RenderContext(
            view=view,
            projection=proj,
            graphics=gfx,
            context_key=key,
            scene=scene,
            camera=camera,
            renderer=window.renderer,
            phase="pick",
        )

        pick_material = window.renderer.pick_material

        # Жёсткое состояние для ID-прохода
        gfx.apply_render_state(RenderState(
            depth_test=True,
            depth_write=True,
            blend=False,
            cull=True,
        ))

        # Рисуем каждую pickable-сущность по очереди, после чего
        # при необходимости блитим промежуточное состояние в debug FBO.
        for ent in scene.entities:
            mr = ent.get_component(MeshRenderer)
            if mr is None:
                continue

            pid = pick_ids.get(ent)
            if pid is None:
                continue

            color = id_to_rgb(pid)
            model = ent.model_matrix()

            pick_material.apply_for_pick(
                model=model,
                view=view,
                proj=proj,
                pick_color=color,
                graphics=gfx,
                context_key=key,
            )

            if mr.mesh is not None:
                mr.mesh.draw(render_ctx)

            if debug_fb is not None and ent.name == debug_symbol:
                self._blit_to_debug(gfx, fb, debug_fb, (pw, ph), key)

    def _blit_to_debug(
        self,
        gfx: "GraphicsBackend",
        src_fb,
        dst_fb,
        size: tuple[int, int],
        context_key: int,
    ) -> None:
        """
        Копирует текущее состояние ID-карты в debug FBO.

        После копирования возвращает привязку к исходному FBO,
        чтобы продолжить проход без изменения состояния.
        """
        blit_fbo_to_fbo(gfx, src_fb, dst_fb, size, context_key)
        gfx.bind_framebuffer(src_fb)
        gfx.set_viewport(0, 0, size[0], size[1])
