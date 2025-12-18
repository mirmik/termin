from __future__ import annotations

from typing import List, Tuple, TYPE_CHECKING

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.framegraph.resource_spec import ResourceSpec
from termin.visualization.core.picking import id_to_rgb
from termin.visualization.core.entity import RenderContext
from termin.visualization.render.renderpass import RenderState
from termin.visualization.render.framegraph.passes.present import blit_fbo_to_fbo
from termin.visualization.render.drawable import Drawable
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle


class IdPass(RenderFramePass):
    """Проход для ID-карты (picking)."""

    inspect_fields = {
        "input_res": InspectField(path="input_res", label="Input Resource", kind="string"),
        "output_res": InspectField(path="output_res", label="Output Resource", kind="string"),
    }

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
        )
        self.input_res = input_res
        self.output_res = output_res

        # Кэш имён отрисовываемых pickable-энтити.
        self._entity_names: List[str] = []

    def _serialize_params(self) -> dict:
        """Сериализует параметры IdPass."""
        return {
            "input_res": self.input_res,
            "output_res": self.output_res,
        }

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "IdPass":
        """Создаёт IdPass из сериализованных данных."""
        return cls(
            input_res=data.get("input_res", "empty"),
            output_res=data.get("output_res", "id"),
            pass_name=data.get("pass_name", "IdPass"),
        )

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        """IdPass читает input_res и пишет output_res inplace."""
        return [(self.input_res, self.output_res)]

    def get_internal_symbols(self) -> List[str]:
        """
        Список имён pickable-сущностей сцены.

        Используется дебаггером для выбора промежуточного состояния
        после прорисовки конкретной сущности в ID-карту.
        """
        return list(self._entity_names)

    def get_resource_specs(self) -> list[ResourceSpec]:
        """
        Объявляет требования к входному ресурсу empty_id.

        Очистка: чёрный цвет (0.0, 0.0, 0.0) + depth=1.0
        """
        return [
            ResourceSpec(
                resource=self.input_res,
                clear_color=(0.0, 0.0, 0.0, 1.0),
                clear_depth=1.0,
            )
        ]

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
        if fb is None:
            return

        # Внутренняя точка дебага
        debug_symbol = self.get_debug_internal_point()
        debugger_window = self.get_debugger_window()

        # Обновляем список имён pickable-сущностей
        self._entity_names = []

        graphics.bind_framebuffer(fb)
        graphics.set_viewport(0, 0, pw, ph)
        graphics.clear_color_depth((0.0, 0.0, 0.0, 0.0))

        # Матрицы камеры для фазовой формулы p_clip = P · V · M · p_local
        view = camera.view_matrix()
        proj = camera.projection_matrix()

        render_ctx = RenderContext(
            view=view,
            projection=proj,
            graphics=graphics,
            context_key=key,
            scene=scene,
            camera=camera,
            phase="pick",
        )

        from termin.visualization.render.materials.pick_material import PickMaterial
        pick_material = PickMaterial()

        # Жёсткое состояние для ID-прохода
        graphics.apply_render_state(RenderState(
            depth_test=True,
            depth_write=True,
            blend=False,
            cull=True,
        ))

        # Рисуем каждую pickable-сущность по очереди
        for ent in scene.entities:
            if not (ent.active and ent.visible):
                continue

            if not ent.is_pickable():
                continue

            # Собираем все Drawable компоненты
            drawables = []
            for component in ent.components:
                if not component.enabled:
                    continue
                if isinstance(component, Drawable):
                    drawables.append(component)

            if not drawables:
                continue

            self._entity_names.append(ent.name)

            pid = ent.pick_id
            color = id_to_rgb(pid)
            model = ent.model_matrix()
            render_ctx.model = model

            pick_material.apply_for_pick(
                model=model,
                view=view,
                proj=proj,
                pick_color=color,
                graphics=graphics,
                context_key=key,
            )

            render_ctx.current_shader = pick_material.shader
            render_ctx.extra_uniforms = {"u_pickColor": ("vec3", color)}

            # Рисуем все Drawable компоненты с одним pick_id
            for drawable in drawables:
                drawable.draw_geometry(render_ctx)

            # TODO: реализовать дебаг через debugger_window

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
