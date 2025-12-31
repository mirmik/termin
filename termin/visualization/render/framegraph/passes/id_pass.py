from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Tuple, TYPE_CHECKING

from termin._native import log
from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.render.framegraph.resource_spec import ResourceSpec
from termin.visualization.core.picking import id_to_rgb
from termin.visualization.render.render_context import RenderContext
from termin.visualization.render.renderpass import RenderState
from termin.visualization.render.system_shaders import get_system_shader
from termin.visualization.render.drawable import Drawable
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle
    from termin.visualization.core.entity import Entity


@dataclass
class PickDrawCall:
    """Pre-collected draw call for IdPass."""
    entity: "Entity"
    drawable: Drawable
    pick_id: int


class IdPass(RenderFramePass):
    """Проход для ID-карты (picking)."""

    _DEBUG_TIMING = False  # Profile timing breakdown
    _DEBUG_DRAW_COUNT = False  # Log draw call count

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

    def _collect_draw_calls(self, scene) -> List[PickDrawCall]:
        """
        Собирает все draw calls для pickable entities.

        Один проход по сцене, плоский список результатов.
        """
        draw_calls: List[PickDrawCall] = []

        for entity in scene.entities:
            if not (entity.active and entity.visible):
                continue

            if not entity.is_pickable():
                continue

            pick_id = entity.pick_id

            for component in entity.components:
                if not component.enabled:
                    continue

                if not isinstance(component, Drawable):
                    continue

                draw_calls.append(PickDrawCall(
                    entity=entity,
                    drawable=component,
                    pick_id=pick_id,
                ))

        return draw_calls

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict[str, "FramebufferHandle" | None],
        writes_fbos: dict[str, "FramebufferHandle | None"],
        rect: tuple[int, int, int, int],
        scene,
        camera,
        context_key: int,
        lights=None,
        canvas=None,
    ):
        px, py, pw, ph = rect

        fb = writes_fbos.get(self.output_res)
        if fb is None:
            return

        graphics.bind_framebuffer(fb)
        graphics.set_viewport(0, 0, pw, ph)
        graphics.clear_color_depth((0.0, 0.0, 0.0, 0.0))

        # Матрицы камеры
        view = camera.view_matrix()
        proj = camera.projection_matrix()

        # Жёсткое состояние для ID-прохода
        graphics.apply_render_state(RenderState(
            depth_test=True,
            depth_write=True,
            blend=False,
            cull=True,
        ))

        # Получаем шейдер из глобального реестра
        shader = get_system_shader("pick", graphics)
        shader.use()
        shader.set_uniform_matrix4("u_view", view)
        shader.set_uniform_matrix4("u_projection", proj)

        # Extra uniforms для передачи в SkinnedMeshRenderer
        extra_uniforms: dict = {}

        # Контекст рендеринга
        render_ctx = RenderContext(
            view=view,
            projection=proj,
            graphics=graphics,
            context_key=context_key,
            scene=scene,
            camera=camera,
            phase="pick",
            current_shader=shader,
            extra_uniforms=extra_uniforms,
        )

        # Собираем draw calls один раз
        draw_calls = self._collect_draw_calls(scene)

        # Обновляем список имён для debug
        self._entity_names = []
        seen_entities = set()

        # Текущий pick_id для батчинга
        current_pick_id = -1
        current_color: tuple = (0.0, 0.0, 0.0)

        # Рисуем все draw calls
        for dc in draw_calls:
            # Re-bind shader before setting uniforms (draw_geometry may switch shaders)
            shader.use()

            # Обновляем pick color только при смене entity
            if dc.pick_id != current_pick_id:
                current_pick_id = dc.pick_id
                current_color = id_to_rgb(dc.pick_id)
                shader.set_uniform_vec3("u_pickColor", current_color)
                # Обновляем extra_uniforms для SkinnedMeshRenderer
                extra_uniforms["u_pickColor"] = ("vec3", current_color)

            # Обновляем model matrix
            model = dc.entity.model_matrix()
            shader.set_uniform_matrix4("u_model", model)
            render_ctx.model = model

            # Debug: track entity names (unique)
            if dc.entity.name not in seen_entities:
                seen_entities.add(dc.entity.name)
                self._entity_names.append(dc.entity.name)

            # Рисуем геометрию
            dc.drawable.draw_geometry(render_ctx)

            # Debugger: блит после отрисовки выбранного символа
            if self.debug_internal_symbol and dc.entity.name == self.debug_internal_symbol:
                self._blit_to_debugger(graphics, fb)

        if self._DEBUG_DRAW_COUNT:
            log.debug(f"[IdPass] draw_calls: {len(draw_calls)}")
