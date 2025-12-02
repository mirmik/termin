"""
RenderEngine — центральный класс для выполнения рендеринга.

Отвечает за:
- Выполнение RenderPipeline для RenderView на RenderSurface
- Управление FBO пулом (через ViewportRenderState)
- Оффскрин рендеринг без окон

Использование:

    # Создание движка
    engine = RenderEngine(graphics)
    
    # Рендер в окно
    engine.render_views(
        surface=WindowRenderSurface(window_handle),
        views=[(view1, state1), (view2, state2)],
    )
    
    # Оффскрин рендер
    offscreen = OffscreenRenderSurface(graphics, 800, 600)
    engine.render_views(
        surface=offscreen,
        views=[(view, state)],
    )
    pixels = offscreen.read_pixels()
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, List, Tuple

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import (
        FramebufferHandle,
        GraphicsBackend,
    )
    from termin.visualization.render.surface import RenderSurface
    from termin.visualization.render.view import RenderView
    from termin.visualization.render.state import ViewportRenderState


class RenderEngine:
    """
    Центральный движок рендеринга.
    
    Выполняет RenderPipeline для набора RenderView на целевой RenderSurface.
    Управляет framegraph и FBO пулами.
    """

    def __init__(self, graphics: "GraphicsBackend"):
        """
        Инициализирует движок рендеринга.
        
        Параметры:
            graphics: Графический бэкенд (OpenGL, Vulkan, etc.)
        """
        self.graphics = graphics

    def render_views(
        self,
        surface: "RenderSurface",
        views: Iterable[Tuple["RenderView", "ViewportRenderState"]],
        present: bool = True,
    ) -> None:
        """
        Рендерит набор views на поверхность.
        
        Алгоритм:
        1. Активирует контекст поверхности
        2. Получает размер и display FBO
        3. Для каждого (view, state) выполняет pipeline
        4. Опционально презентует результат (swap buffers)
        
        Параметры:
            surface: Целевая поверхность рендеринга.
            views: Итератор пар (RenderView, ViewportRenderState).
            present: Вызывать ли surface.present() после рендера.
        """
        self.graphics.ensure_ready()
        surface.make_current()

        width, height = surface.get_size()
        display_fbo = surface.get_framebuffer()
        context_key = surface.context_key()

        for view, state in views:
            self._render_single_view(
                view=view,
                state=state,
                framebuffer_size=(width, height),
                display_fbo=display_fbo,
                context_key=context_key,
            )

        if present:
            surface.present()

    def render_single_view(
        self,
        surface: "RenderSurface",
        view: "RenderView",
        state: "ViewportRenderState",
        present: bool = True,
    ) -> None:
        """
        Рендерит один view на поверхность.
        
        Удобная обёртка для случая одного view.
        
        Параметры:
            surface: Целевая поверхность.
            view: Что рендерим.
            state: Состояние рендера (pipeline, fbos).
            present: Вызывать ли present() после рендера.
        """
        self.render_views(surface, [(view, state)], present=present)

    def _render_single_view(
        self,
        view: "RenderView",
        state: "ViewportRenderState",
        framebuffer_size: Tuple[int, int],
        display_fbo: "FramebufferHandle",
        context_key: int,
    ) -> None:
        """
        Внутренний метод рендеринга одного view.
        
        Выполняет framegraph schedule для pipeline из state.
        
        Параметры:
            view: RenderView (сцена, камера, rect).
            state: ViewportRenderState (pipeline, fbos).
            framebuffer_size: Размер целевого буфера (width, height).
            display_fbo: FBO экрана/окна.
            context_key: Ключ контекста для кэширования.
        """
        from termin.visualization.render.framegraph import FrameGraph, RenderFramePass

        pipeline = state.pipeline
        if pipeline is None:
            return

        frame_passes = pipeline.passes
        if not frame_passes:
            return

        # Вычисляем пиксельный rect для view
        width, height = framebuffer_size
        px, py, pw, ph = view.compute_pixel_rect(width, height)

        # Обновляем aspect ratio камеры
        view.camera.set_aspect(pw / float(max(1, ph)))

        # Запрашиваем required_resources у render passes
        for render_pass in frame_passes:
            if isinstance(render_pass, RenderFramePass):
                render_pass.required_resources()

        # Строим framegraph schedule
        graph = FrameGraph(frame_passes)
        schedule = graph.build_schedule()
        alias_groups = graph.fbo_alias_groups()

        # Управляем FBO пулом через state
        fbos = state.fbos
        fbos["DISPLAY"] = display_fbo

        for canon, names in alias_groups.items():
            if canon == "DISPLAY":
                for name in names:
                    fbos[name] = display_fbo
                continue

            fb = self._ensure_fbo(state, canon, (pw, ph))
            for name in names:
                fbos[name] = fb

        # Выполняем clear спецификации
        for clear_spec in pipeline.clear_specs:
            fb = fbos.get(clear_spec.resource)
            if fb is None:
                continue
            self.graphics.bind_framebuffer(fb)
            self.graphics.set_viewport(0, 0, pw, ph)
            if clear_spec.color is not None and clear_spec.depth is not None:
                self.graphics.clear_color_depth(clear_spec.color)
            elif clear_spec.color is not None:
                self.graphics.clear_color(clear_spec.color)
            elif clear_spec.depth is not None:
                self.graphics.clear_depth(clear_spec.depth)

        # Выполняем пассы
        scene = view.scene
        lights = scene.build_lights()

        for render_pass in schedule:
            pass_reads = {name: fbos.get(name) for name in render_pass.reads}
            pass_writes = {name: fbos.get(name) for name in render_pass.writes}

            render_pass.execute(
                self.graphics,
                reads_fbos=pass_reads,
                writes_fbos=pass_writes,
                rect=(px, py, pw, ph),
                scene=scene,
                camera=view.camera,
                context_key=context_key,
                lights=lights,
                canvas=view.canvas,
            )

    def _ensure_fbo(
        self,
        state: "ViewportRenderState",
        key: str,
        size: Tuple[int, int],
    ) -> "FramebufferHandle":
        """
        Получает или создаёт FBO для ресурса.
        
        Параметры:
            state: ViewportRenderState с FBO пулом.
            key: Имя ресурса.
            size: Требуемый размер (width, height).
        
        Возвращает:
            FramebufferHandle подходящего размера.
        """
        framebuffer = state.fbos.get(key)
        if framebuffer is None:
            framebuffer = self.graphics.create_framebuffer(size)
            state.fbos[key] = framebuffer
        else:
            framebuffer.resize(size)
        return framebuffer
