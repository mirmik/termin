from __future__ import annotations

from typing import List

from termin.visualization.render.framegraph.context import FrameContext
from termin.visualization.render.framegraph.passes.base import RenderFramePass
from termin.visualization.core.entity import RenderContext
from termin.visualization.render.components import MeshRenderer


class ColorPass(RenderFramePass):
    """
    Основной цветовой проход рендеринга.

    Рисует все сущности сцены с MeshRenderer, последовательно обходя их.
    Поддерживает внутренние точки дебага — для каждого меша можно получить
    промежуточное состояние рендера (до отрисовки следующих мешей).

    Атрибуты:
        input_res: Имя входного ресурса (обычно "empty" — пустой FBO).
        output_res: Имя выходного ресурса (обычно "color").
    """

    def __init__(
        self,
        input_res: str = "empty",
        output_res: str = "color",
        pass_name: str = "Color",
    ):
        super().__init__(
            pass_name=pass_name,
            reads={input_res},
            writes={output_res},
            inplace=True,  # логически — модификатор состояния ресурса
        )
        self.input_res = input_res
        self.output_res = output_res

        # Кэш имён сущностей с MeshRenderer для текущей сцены.
        # Обновляется при каждом execute().
        self._entity_names: List[str] = []

    def get_internal_symbols(self) -> List[str]:
        """
        Возвращает список имён сущностей с MeshRenderer.

        Эти имена можно использовать как точки дебага — при выборе
        соответствующего символа в дебаггере будет блититься состояние
        рендера после отрисовки этого меша.

        Список обновляется при каждом выполнении пасса.
        """
        return list(self._entity_names)

    def execute(self, ctx: FrameContext):
        """
        Выполняет цветовой проход.

        Алгоритм:
        1. Подготавливает FBO и очищает его цветом фона сцены.
        2. Обходит все сущности сцены.
        3. Для каждой сущности с MeshRenderer вызывает отрисовку.
        4. Если установлена внутренняя точка дебага и текущая сущность
           соответствует выбранному символу — блитит состояние в debug FBO.

        Формула преобразования координат (модель → клип):
            p_clip = P · V · M · p_local

        где:
            M — матрица модели (model_matrix сущности)
            V — матрица вида камеры (view)
            P — матрица проекции (projection)
        """
        gfx = ctx.graphics
        window = ctx.window
        viewport = ctx.viewport
        scene = viewport.scene
        lights = ctx.lights
        if lights is not None:
            scene.lights = lights
        camera = viewport.camera
        px, py, pw, ph = ctx.rect
        key = ctx.context_key

        # Подготовка выходного FBO
        fb = window.get_viewport_fbo(viewport, self.output_res, (pw, ph))
        ctx.fbos[self.output_res] = fb

        gfx.bind_framebuffer(fb)
        gfx.set_viewport(0, 0, pw, ph)
        gfx.clear_color_depth(scene.background_color)

        # Матрицы камеры
        view = camera.get_view_matrix()
        projection = camera.get_projection_matrix()

        # Контекст рендеринга для компонентов
        render_context = RenderContext(
            view=view,
            projection=projection,
            camera=camera,
            scene=scene,
            renderer=window.renderer,
            context_key=key,
            graphics=gfx,
        )

        # Получаем конфигурацию внутренней точки дебага
        debug_symbol, debug_output = self.get_debug_internal_point()

        # Подготавливаем debug FBO если нужно
        debug_fb = None
        if debug_symbol is not None and debug_output is not None:
            debug_fb = window.get_viewport_fbo(viewport, debug_output, (pw, ph))
            ctx.fbos[debug_output] = debug_fb

        # Обновляем кэш имён сущностей
        self._entity_names = []

        # Обход сущностей сцены и отрисовка
        for entity in scene.entities:
            # Сохраняем имя сущности (для get_internal_symbols)
            self._entity_names.append(entity.name)

            # Отрисовка сущности
            entity.draw(render_context)

            # Если текущая сущность — точка дебага, блитим в debug FBO
            if debug_fb is not None and entity.name == debug_symbol:
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
        Копирует текущее состояние color FBO в debug FBO.

        Использует фуллскрин-квад для блиттинга текстуры.
        После копирования восстанавливает привязку к исходному FBO.

        Параметры:
            gfx: Графический бэкенд.
            src_fb: Исходный FBO (откуда копируем).
            dst_fb: Целевой FBO (куда копируем).
            size: Размер в пикселях (width, height).
            context_key: Ключ контекста для VAO кэша.
        """
        from termin.visualization.render.framegraph.passes.present import blit_fbo_to_fbo

        # Блитим src_fb -> dst_fb
        blit_fbo_to_fbo(gfx, src_fb, dst_fb, size, context_key)

        # Восстанавливаем привязку к основному FBO для продолжения рендера
        gfx.bind_framebuffer(src_fb)
        gfx.set_viewport(0, 0, size[0], size[1])
