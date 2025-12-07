from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple, TYPE_CHECKING

import numpy as np

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.core.entity import RenderContext
from termin.visualization.render.components import MeshRenderer

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle
    from termin.visualization.render.framegraph.resource import ShadowMapArrayResource
    from termin.visualization.core.material import MaterialPhase
    from termin.visualization.core.entity import Entity


# Максимальное количество shadow maps в шейдере
MAX_SHADOW_MAPS = 4

# Начальный texture unit для shadow maps (после обычных текстур)
SHADOW_MAP_TEXTURE_UNIT_START = 8


@dataclass
class PhaseDrawCall:
    """
    Описание одного draw call для фазы.

    Атрибуты:
        entity: Сущность, которой принадлежит фаза
        mesh_renderer: MeshRenderer компонент
        phase: Фаза материала для отрисовки
        priority: Приоритет отрисовки (меньше = раньше)
    """
    entity: "Entity"
    mesh_renderer: MeshRenderer
    phase: "MaterialPhase"
    priority: int


class ColorPass(RenderFramePass):
    """
    Основной цветовой проход рендеринга.

    Рисует все сущности сцены с MeshRenderer, фильтруя фазы материалов
    по phase_mark и сортируя по priority.

    Поддерживает shadow mapping — читает ShadowMapArray и передаёт
    текстуры и матрицы в шейдеры.

    Атрибуты:
        input_res: Имя входного ресурса (обычно "empty" — пустой FBO).
        output_res: Имя выходного ресурса (обычно "color").
        shadow_res: Имя ресурса ShadowMapArray (опционально).
        phase_mark: Метка фазы для фильтрации ("opaque", "transparent" и т.д.).
                    Если None, рендерит все фазы (legacy режим).
    """

    def __init__(
        self,
        input_res: str = "empty",
        output_res: str = "color",
        shadow_res: str | None = "shadow_maps",
        pass_name: str = "Color",
        phase_mark: str | None = None,
    ):
        reads = {input_res}
        if shadow_res is not None:
            reads.add(shadow_res)

        super().__init__(
            pass_name=pass_name,
            reads=reads,
            writes={output_res},
        )
        self.input_res = input_res
        self.output_res = output_res
        self.shadow_res = shadow_res
        self.phase_mark = phase_mark

        # Кэш имён сущностей с MeshRenderer
        self._entity_names: List[str] = []

    def _collect_draw_calls(self, scene, phase_mark: str | None) -> List[PhaseDrawCall]:
        """
        Собирает все draw calls для указанной метки фазы.

        Алгоритм:
        1. Обходит все entities сцены
        2. Для каждой entity с MeshRenderer получает фазы материала
        3. Фильтрует фазы по phase_mark (если задан)
        4. Возвращает список PhaseDrawCall отсортированный по priority

        Параметры:
            scene: Сцена с entities
            phase_mark: Метка фазы для фильтрации (None = все фазы)

        Возвращает:
            Список PhaseDrawCall отсортированный по priority
        """
        draw_calls: List[PhaseDrawCall] = []

        for entity in scene.entities:
            if not (entity.active and entity.visible):
                continue

            mr = entity.get_component(MeshRenderer)
            if mr is None or not mr.enabled:
                continue

            # Получаем фазы из MeshRenderer
            phases = mr.get_phases_for_mark(phase_mark)
            for phase in phases:
                draw_calls.append(PhaseDrawCall(
                    entity=entity,
                    mesh_renderer=mr,
                    phase=phase,
                    priority=phase.priority,
                ))

        # Сортируем по priority (меньше = раньше)
        draw_calls.sort(key=lambda dc: dc.priority)
        return draw_calls

    def get_inplace_aliases(self) -> List[Tuple[str, str]]:
        """ColorPass читает input_res и пишет output_res inplace."""
        return [(self.input_res, self.output_res)]

    def get_internal_symbols(self) -> List[str]:
        """
        Возвращает список имён сущностей с MeshRenderer.

        Эти имена можно использовать как точки дебага — при выборе
        соответствующего символа в дебаггере будет блититься состояние
        рендера после отрисовки этого меша.
        """
        return list(self._entity_names)

    def _bind_shadow_maps(
        self,
        graphics: "GraphicsBackend",
        shadow_array: "ShadowMapArrayResource | None",
    ) -> None:
        """
        Биндит shadow map текстуры на texture units.
        
        Shadow maps биндятся начиная с SHADOW_MAP_TEXTURE_UNIT_START.
        MeshRenderer будет загружать uniform'ы при отрисовке.
        """
        if shadow_array is None or len(shadow_array) == 0:
            return
        
        for i, entry in enumerate(shadow_array):
            if i >= MAX_SHADOW_MAPS:
                break
            
            unit = SHADOW_MAP_TEXTURE_UNIT_START + i
            texture = entry.texture()
            texture.bind(unit)

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict[str, "FramebufferHandle | None"],
        writes_fbos: dict[str, "FramebufferHandle | None"],
        rect: tuple[int, int, int, int],
        scene,
        camera,
        context_key: int,
        lights=None,
        canvas=None,
    ):
        """
        Выполняет цветовой проход.

        Алгоритм (режим с phase_mark):
        1. Получает ShadowMapArray (если есть) и биндит текстуры
        2. Подготавливает FBO
        3. Собирает все draw calls для указанной phase_mark
        4. Сортирует draw calls по priority
        5. Для каждого draw call:
           a. Применяет материал (фазу)
           b. Загружает shadow uniforms
           c. Вызывает отрисовку меша

        Алгоритм (legacy режим, phase_mark=None):
        - Обходит все сущности и вызывает entity.draw()

        Формула преобразования координат (модель → клип):
            p_clip = P · V · M · p_local

        где:
            M — матрица модели (model_matrix сущности)
            V — матрица вида камеры (view)
            P — матрица проекции (projection)
        """
        from termin.visualization.render.lighting.upload import upload_lights_to_shader, upload_ambient_to_shader
        from termin.visualization.render.lighting.shadow_upload import upload_shadow_maps_to_shader
        from termin.visualization.render.renderpass import RenderState

        if lights is not None:
            scene.lights = lights

        px, py, pw, ph = rect
        key = context_key

        fb = writes_fbos.get(self.output_res)
        if fb is None:
            return

        # Получаем ShadowMapArrayResource
        shadow_array = None
        if self.shadow_res is not None:
            shadow_array = reads_fbos.get(self.shadow_res)
            # Проверяем тип — должен быть ShadowMapArrayResource
            from termin.visualization.render.framegraph.resource import ShadowMapArrayResource
            if not isinstance(shadow_array, ShadowMapArrayResource):
                shadow_array = None

        # Биндим shadow maps на texture units
        self._bind_shadow_maps(graphics, shadow_array)

        graphics.bind_framebuffer(fb)
        graphics.set_viewport(0, 0, pw, ph)

        # Матрицы камеры
        view = camera.get_view_matrix()
        projection = camera.get_projection_matrix()

        # Контекст рендеринга для компонентов
        # Передаём shadow_data и phase для использования в MeshRenderer
        render_context = RenderContext(
            view=view,
            projection=projection,
            camera=camera,
            scene=scene,
            context_key=key,
            graphics=graphics,
            shadow_data=shadow_array,
            phase=self.phase_mark if self.phase_mark else "main",
        )

        # Получаем конфигурацию внутренней точки дебага
        debug_symbol, debug_output = self.get_debug_internal_point()

        # Подготавливаем debug FBO если нужно
        debug_fb = None
        if debug_symbol is not None and debug_output is not None:
            debug_fb = writes_fbos.get(debug_output)

        # Обновляем кэш имён сущностей
        self._entity_names = []

        # Режим с phase_mark — собираем и сортируем draw calls
        if self.phase_mark is not None:
            draw_calls = self._collect_draw_calls(scene, self.phase_mark)

            for dc in draw_calls:
                self._entity_names.append(dc.entity.name)

                # Получаем матрицу модели
                model = dc.entity.model_matrix()

                # Применяем render state фазы
                graphics.apply_render_state(dc.phase.render_state)

                # Применяем материал (фазу)
                dc.phase.apply(model, view, projection, graphics, context_key=key)

                # Загружаем свет и тени
                shader = dc.phase.shader_programm
                upload_lights_to_shader(shader, scene.lights)
                upload_ambient_to_shader(shader, scene.ambient_color, scene.ambient_intensity)
                if shadow_array is not None:
                    upload_shadow_maps_to_shader(shader, shadow_array)

                # Рисуем меш
                if dc.mesh_renderer.mesh is not None:
                    dc.mesh_renderer.mesh.draw(render_context)

                if debug_fb is not None and dc.entity.name == debug_symbol:
                    self._blit_to_debug(graphics, fb, debug_fb, (pw, ph), key)

            # Сбрасываем render state
            graphics.apply_render_state(RenderState())

        else:
            # Legacy режим — вызываем entity.draw()
            for entity in scene.entities:
                self._entity_names.append(entity.name)

                entity.draw(render_context)

                if debug_fb is not None and entity.name == debug_symbol:
                    self._blit_to_debug(graphics, fb, debug_fb, (pw, ph), key)

    def _blit_to_debug(
        self,
        gfx: "GraphicsBackend",
        src_fb,
        dst_fb,
        size: tuple[int, int],
        context_key: int,
    ) -> None:
        """
        Копирует текущее состояние color FBO в debug FBO.
        """
        from termin.visualization.render.framegraph.passes.present import blit_fbo_to_fbo

        blit_fbo_to_fbo(gfx, src_fb, dst_fb, size, context_key)

        gfx.bind_framebuffer(src_fb)
        gfx.set_viewport(0, 0, size[0], size[1])
