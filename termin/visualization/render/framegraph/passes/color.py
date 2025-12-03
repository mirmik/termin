from __future__ import annotations

from typing import List, TYPE_CHECKING

import numpy as np

from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.core.entity import RenderContext
from termin.visualization.render.components import MeshRenderer

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle
    from termin.visualization.render.shadow.shadow_map_array import ShadowMapArray


# Максимальное количество shadow maps в шейдере
MAX_SHADOW_MAPS = 4

# Начальный texture unit для shadow maps (после обычных текстур)
SHADOW_MAP_TEXTURE_UNIT_START = 8


class ColorPass(RenderFramePass):
    """
    Основной цветовой проход рендеринга.

    Рисует все сущности сцены с MeshRenderer, последовательно обходя их.
    Поддерживает shadow mapping — читает ShadowMapArray и передаёт
    текстуры и матрицы в шейдеры.

    Атрибуты:
        input_res: Имя входного ресурса (обычно "empty" — пустой FBO).
        output_res: Имя выходного ресурса (обычно "color").
        shadow_res: Имя ресурса ShadowMapArray (опционально).
    """

    def __init__(
        self,
        input_res: str = "empty",
        output_res: str = "color",
        shadow_res: str | None = "shadow_maps",
        pass_name: str = "Color",
    ):
        reads = {input_res}
        if shadow_res is not None:
            reads.add(shadow_res)
        
        super().__init__(
            pass_name=pass_name,
            reads=reads,
            writes={output_res},
            inplace=False,  # Читаем несколько ресурсов, пишем в другой
        )
        self.input_res = input_res
        self.output_res = output_res
        self.shadow_res = shadow_res

        # Кэш имён сущностей с MeshRenderer
        self._entity_names: List[str] = []

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
        shadow_array: "ShadowMapArray | None",
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

        Алгоритм:
        1. Получает ShadowMapArray (если есть) и биндит текстуры
        2. Подготавливает FBO
        3. Обходит все сущности сцены
        4. Для каждой сущности с MeshRenderer:
           a. Применяет материал
           b. Загружает shadow uniforms
           c. Вызывает отрисовку

        Формула преобразования координат (модель → клип):
            p_clip = P · V · M · p_local

        где:
            M — матрица модели (model_matrix сущности)
            V — матрица вида камеры (view)
            P — матрица проекции (projection)
        """
        if lights is not None:
            scene.lights = lights

        px, py, pw, ph = rect
        key = context_key

        fb = writes_fbos.get(self.output_res)
        if fb is None:
            return

        # Получаем ShadowMapArray
        shadow_array = None
        if self.shadow_res is not None:
            shadow_array = reads_fbos.get(self.shadow_res)
            # Проверяем тип — должен быть ShadowMapArray, а не FBO
            from termin.visualization.render.shadow.shadow_map_array import ShadowMapArray
            if not isinstance(shadow_array, ShadowMapArray):
                shadow_array = None

        # Биндим shadow maps на texture units
        self._bind_shadow_maps(graphics, shadow_array)

        graphics.bind_framebuffer(fb)
        graphics.set_viewport(0, 0, pw, ph)

        # Матрицы камеры
        view = camera.get_view_matrix()
        projection = camera.get_projection_matrix()

        # Контекст рендеринга для компонентов
        # Передаём shadow_data для использования в MeshRenderer
        render_context = RenderContext(
            view=view,
            projection=projection,
            camera=camera,
            scene=scene,
            context_key=key,
            graphics=graphics,
            shadow_data=shadow_array,
        )

        # Получаем конфигурацию внутренней точки дебага
        debug_symbol, debug_output = self.get_debug_internal_point()

        # Подготавливаем debug FBO если нужно
        debug_fb = None
        if debug_symbol is not None and debug_output is not None:
            debug_fb = writes_fbos.get(debug_output)

        # Обновляем кэш имён сущностей
        self._entity_names = []

        # Обход сущностей сцены и отрисовка
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
