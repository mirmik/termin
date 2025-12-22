"""
RenderEngine — центральный класс для выполнения рендеринга.

Отвечает за:
- Выполнение RenderPipeline для RenderView на RenderSurface
- Управление пулом ресурсов (FBO, ShadowMapArray и др.) через ViewportRenderState
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

Ресурсы конвейера:
- По умолчанию ресурс — это FBO размера viewport'а
- Пассы могут объявлять спецификации ресурсов через get_resource_specs()
- Тип ресурса определяется полем resource_type в ResourceSpec:
  - "fbo" (по умолчанию) — стандартный framebuffer
  - "shadow_map_array" — массив shadow maps, создаётся пассом динамически
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable, List, Tuple

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
        self._logged_errors: set[str] = set()  # Кэш уже залогированных ошибок

    def clear_error_cache(self) -> None:
        """Сбрасывает кэш ошибок (вызывать при смене пайплайна)."""
        self._logged_errors.clear()

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
        from termin.core.profiler import Profiler
        profiler = Profiler.instance()

        with profiler.section("Render"):
            self.graphics.ensure_ready()
            surface.make_current()

            width, height = surface.get_size()
            display_fbo = surface.get_framebuffer()
            context_key = surface.context_key()

            # Регистрируем контекст для корректного удаления GPU ресурсов
            from termin.visualization.platform.backends.opengl import register_context
            register_context(context_key, surface.make_current)

            for view, state in views:
                try:
                    self._render_single_view(
                        view=view,
                        state=state,
                        framebuffer_size=(width, height),
                        display_fbo=display_fbo,
                        context_key=context_key,
                    )
                except Exception as e:
                    error_msg = str(e)
                    if error_msg not in self._logged_errors:
                        self._logged_errors.add(error_msg)
                        import logging
                        import traceback
                        logger = logging.getLogger(__name__)
                        tb = traceback.format_exc()
                        logger.error(f"Pipeline error: {e}\n{tb}")
                        print(f"Pipeline error: {e}\n{tb}")

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

        # Есть две механики передачи спеков. Спеки может объявить тот, кто собирал pipeline,
        # или каждый pass может объявить свои спеки. Собираем все спеки в одну мапу.
        # Pipeline-level specs имеют приоритет над pass specs.
        resource_specs_map = {}  # resource_name -> ResourceSpec

        # Сначала собираем ResourceSpec'ы из всех pass'ов
        for render_pass in frame_passes:
            if isinstance(render_pass, RenderFramePass):
                for spec in render_pass.get_resource_specs():
                    resource_specs_map[spec.resource] = spec

        # Затем добавляем pipeline-level ResourceSpec'ы (они имеют приоритет)
        if pipeline.pipeline_specs:
            for spec in pipeline.pipeline_specs:
                resource_specs_map[spec.resource] = spec

        # Управляем пулом ресурсов через state
        # fbos — это словарь ресурсов (FBO, ShadowMapArray и др.)
        resources = state.fbos
        resources["DISPLAY"] = display_fbo

        for canon, names in alias_groups.items():
            if canon == "DISPLAY":
                for name in names:
                    resources[name] = display_fbo
                continue

            # Проверяем тип ресурса из спека — ищем по canonical name или по любому alias
            spec = resource_specs_map.get(canon)
            if spec is None:
                # Ищем spec по любому имени из alias группы
                for name in names:
                    if name in resource_specs_map:
                        spec = resource_specs_map[name]
                        break

            resource_type = "fbo"
            if spec is not None:
                resource_type = spec.resource_type

            # Для не-FBO ресурсов пропускаем автоматическое создание
            # Пасс сам создаст и положит ресурс в словарь
            if resource_type != "fbo":
                for name in names:
                    if name not in resources:
                        resources[name] = None
                continue

            # Определяем размер и samples из ResourceSpec
            resource_size = (pw, ph)
            resource_samples = 1
            if spec is not None:
                if spec.size is not None:
                    resource_size = spec.size
                resource_samples = spec.samples

            fb = self._ensure_fbo(state, canon, resource_size, resource_samples)
            for name in names:
                resources[name] = fb

        # Выполняем очистку ресурсов согласно ResourceSpec (только для FBO)
        for resource_name, spec in resource_specs_map.items():
            # Пропускаем не-FBO ресурсы
            if spec.resource_type != "fbo":
                continue

            if spec.clear_color is None and spec.clear_depth is None:
                continue  # Нечего очищать

            fb = resources.get(resource_name)
            if fb is None:
                continue

            self.graphics.bind_framebuffer(fb)

            # Определяем размер viewport для очистки
            fb_size = spec.size if spec.size is not None else (pw, ph)
            self.graphics.set_viewport(0, 0, fb_size[0], fb_size[1])

            if spec.clear_color is not None and spec.clear_depth is not None:
                self.graphics.clear_color_depth(spec.clear_color)
            elif spec.clear_color is not None:
                self.graphics.clear_color(spec.clear_color)
            elif spec.clear_depth is not None:
                self.graphics.clear_depth(spec.clear_depth)

        # Выполняем пассы
        scene = view.scene
        lights = scene.build_lights()

        # Debug: log first frames (controlled by pass-level flag)
        from termin.visualization.render.framegraph.passes.color import ColorPass
        if ColorPass._DEBUG_FIRST_FRAMES and ColorPass._debug_frame_count < 5:
            print(f"\n=== RenderEngine.build_lights ===")
            print(f"  light_components count: {len(scene.light_components)}")
            print(f"  built lights count: {len(lights)}")
            for i, lt in enumerate(lights):
                print(f"  Light[{i}]: type={lt.type}, dir={lt.direction}, pos={lt.position}")
            print(f"=== end ===\n")

        from termin.core.profiler import Profiler
        profiler = Profiler.instance()

        for render_pass in schedule:
            # Сброс GL-состояния перед каждым пассом
            self.graphics.reset_state()

            pass_reads = {name: resources.get(name) for name in render_pass.reads}
            pass_writes = {name: resources.get(name) for name in render_pass.writes}

            with profiler.section(render_pass.pass_name):
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

            # После выполнения пасса обновляем ресурсы в пуле
            # (пасс мог создать новые ресурсы, например ShadowMapArray)
            for name in render_pass.writes:
                if name in pass_writes and pass_writes[name] is not None:
                    resources[name] = pass_writes[name]

    def _ensure_fbo(
        self,
        state: "ViewportRenderState",
        key: str,
        size: Tuple[int, int],
        samples: int = 1,
    ) -> "FramebufferHandle":
        """
        Получает или создаёт FBO для ресурса.

        Параметры:
            state: ViewportRenderState с FBO пулом.
            key: Имя ресурса.
            size: Требуемый размер (width, height).
            samples: Количество MSAA samples (1 = без MSAA).

        Возвращает:
            FramebufferHandle подходящего размера.
        """
        framebuffer = state.fbos.get(key)
        if framebuffer is None:
            framebuffer = self.graphics.create_framebuffer(size, samples=samples)
            state.fbos[key] = framebuffer
        else:
            # TODO: пересоздать FBO если изменился samples
            framebuffer.resize(size)
        return framebuffer
