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
  - "shadow_map_array" — массив shadow maps
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Tuple

from termin.visualization.render.framegraph.resource import ShadowMapArrayResource
from termin.visualization.render.framegraph.execute_context import ExecuteContext

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import (
        FramebufferHandle,
        GraphicsBackend,
    )
    from termin.visualization.render.surface import RenderSurface
    from termin.visualization.render.view import RenderView
    from termin.visualization.render.state import ViewportRenderState
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.camera import CameraComponent
    from termin.visualization.ui.canvas import Canvas
    from termin.visualization.render.framegraph import RenderPipeline


@dataclass
class ViewportContext:
    """
    Контекст viewport для рендеринга в scene pipeline.

    Содержит данные одного viewport, необходимые для выполнения пассов.
    """
    name: str
    camera: "CameraComponent"
    rect: Tuple[int, int, int, int]  # (px, py, pw, ph) in pixels
    canvas: Optional["Canvas"] = None
    layer_mask: int = 0xFFFFFFFFFFFFFFFF
    output_fbo: Optional["FramebufferHandle"] = None  # Target FBO for offscreen rendering


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
            from termin.visualization.platform.backends import register_context
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
                        from termin._native import log
                        import traceback
                        tb = traceback.format_exc()
                        log.error(f"Pipeline error: {e}\n{tb}")

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

        Выполняет framegraph schedule для pipeline из view.

        Параметры:
            view: RenderView (сцена, камера, rect, pipeline).
            state: ViewportRenderState (fbos).
            framebuffer_size: Размер целевого буфера (width, height).
            display_fbo: FBO экрана/окна.
            context_key: Ключ контекста для кэширования.
        """
        from termin.visualization.render.framegraph import FrameGraph, RenderFramePass

        pipeline = view.pipeline
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

            # Для shadow_map_array создаём ShadowMapArrayResource
            if resource_type == "shadow_map_array":
                # Берём resolution из spec.size (квадратная текстура)
                resolution = 1024
                if spec is not None and spec.size is not None:
                    resolution = spec.size[0]  # width = height для shadow map

                shadow_array = state.get_shadow_map_array(canon)
                if shadow_array is None or shadow_array.resolution != resolution:
                    shadow_array = ShadowMapArrayResource(resolution=resolution)
                    state.set_shadow_map_array(canon, shadow_array)
                for name in names:
                    resources[name] = shadow_array
                continue

            # Для других не-FBO ресурсов пропускаем
            if resource_type != "fbo":
                for name in names:
                    if name not in resources:
                        resources[name] = None
                continue

            # Определяем размер, samples и format из ResourceSpec
            resource_size = (pw, ph)
            resource_samples = 1
            resource_format = ""
            if spec is not None:
                if spec.size is not None:
                    resource_size = spec.size
                resource_samples = spec.samples
                if spec.format is not None:
                    resource_format = spec.format

            fb = self._ensure_fbo(state, canon, resource_size, resource_samples, resource_format)
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

        from termin.core.profiler import Profiler
        profiler = Profiler.instance()

        for render_pass in schedule:
            # Сброс GL-состояния перед каждым пассом
            self.graphics.reset_state()

            # Очищаем pending GL ошибки перед пассом
            self._clear_gl_errors()

            pass_reads = {name: resources.get(name) for name in render_pass.reads}
            pass_writes = {name: resources.get(name) for name in render_pass.writes}

            ctx = ExecuteContext(
                graphics=self.graphics,
                reads_fbos=pass_reads,
                writes_fbos=pass_writes,
                rect=(px, py, pw, ph),
                scene=scene,
                camera=view.camera,
                context_key=context_key,
                lights=lights,
                canvas=view.canvas,
                layer_mask=view.layer_mask,
            )

            with profiler.section(render_pass.pass_name):
                render_pass.execute(ctx)

            # Проверяем GL ошибки после пасса
            self._check_gl_errors(render_pass.pass_name)

            # После выполнения пасса обновляем ресурсы в пуле
            # (пасс мог создать новые ресурсы, например ShadowMapArray)
            for name in render_pass.writes:
                if name in pass_writes and pass_writes[name] is not None:
                    resources[name] = pass_writes[name]

    def render_scene_pipeline(
        self,
        surface: "RenderSurface",
        pipeline: "RenderPipeline",
        scene: "Scene",
        viewport_contexts: Dict[str, ViewportContext],
        state: "ViewportRenderState",
        default_viewport: str = "",
        present: bool = False,
    ) -> None:
        """
        Выполняет scene pipeline один раз с несколькими viewport контекстами.

        Scene pipeline может содержать пассы, нацеленные на разные viewport'ы.
        Каждый pass объявляет viewport_name, и этот метод выбирает соответствующий
        контекст (camera, rect, canvas) для каждого pass'а.

        Параметры:
            surface: Целевая поверхность рендеринга.
            pipeline: Scene pipeline для выполнения.
            scene: Сцена с объектами.
            viewport_contexts: Словарь viewport_name -> ViewportContext.
            state: ViewportRenderState с пулом FBO.
            default_viewport: Имя viewport по умолчанию для пассов без viewport_name.
            present: Вызывать ли surface.present() после рендера.
        """
        from termin.core.profiler import Profiler
        from termin._native import log

        profiler = Profiler.instance()

        with profiler.section("RenderScenePipeline"):
            self.graphics.ensure_ready()
            surface.make_current()

            width, height = surface.get_size()
            display_fbo = surface.get_framebuffer()
            context_key = surface.context_key()

            from termin.visualization.platform.backends import register_context
            register_context(context_key, surface.make_current)

            try:
                self._execute_scene_pipeline(
                    pipeline=pipeline,
                    scene=scene,
                    viewport_contexts=viewport_contexts,
                    state=state,
                    default_viewport=default_viewport,
                    framebuffer_size=(width, height),
                    display_fbo=display_fbo,
                    context_key=context_key,
                )
            except Exception as e:
                error_msg = str(e)
                if error_msg not in self._logged_errors:
                    self._logged_errors.add(error_msg)
                    import traceback
                    tb = traceback.format_exc()
                    log.error(f"Scene pipeline error: {e}\n{tb}")

            if present:
                surface.present()

    def _execute_scene_pipeline(
        self,
        pipeline: "RenderPipeline",
        scene: "Scene",
        viewport_contexts: Dict[str, ViewportContext],
        state: "ViewportRenderState",
        default_viewport: str,
        framebuffer_size: Tuple[int, int],
        display_fbo: "FramebufferHandle",
        context_key: int,
    ) -> None:
        """
        Внутренний метод выполнения scene pipeline.

        Параметры:
            pipeline: Pipeline для выполнения.
            scene: Сцена.
            viewport_contexts: Контексты viewport'ов.
            state: Состояние рендера.
            default_viewport: Viewport по умолчанию.
            framebuffer_size: Размер surface.
            display_fbo: FBO экрана.
            context_key: Ключ контекста.
        """
        from termin.visualization.render.framegraph import FrameGraph, RenderFramePass
        from termin._native import log

        frame_passes = pipeline.passes
        if not frame_passes:
            return

        # Выбираем первый доступный viewport как default, если не указан
        if not default_viewport and viewport_contexts:
            default_viewport = next(iter(viewport_contexts.keys()))

        default_ctx = viewport_contexts.get(default_viewport)
        if default_ctx is None and viewport_contexts:
            default_ctx = next(iter(viewport_contexts.values()))

        if default_ctx is None:
            log.error("[_execute_scene_pipeline] No viewport contexts provided")
            return

        # Обновляем aspect ratio для всех камер
        for ctx in viewport_contexts.values():
            px, py, pw, ph = ctx.rect
            ctx.camera.set_aspect(pw / float(max(1, ph)))

        # Запрашиваем required_resources у render passes
        for render_pass in frame_passes:
            if isinstance(render_pass, RenderFramePass):
                render_pass.required_resources()

        # Строим framegraph schedule
        graph = FrameGraph(frame_passes)
        schedule = graph.build_schedule()
        alias_groups = graph.fbo_alias_groups()

        # Собираем ResourceSpecs
        resource_specs_map = {}
        for render_pass in frame_passes:
            for spec in render_pass.get_resource_specs():
                resource_specs_map[spec.resource] = spec
        if pipeline.pipeline_specs:
            for spec in pipeline.pipeline_specs:
                resource_specs_map[spec.resource] = spec

        # Управляем пулом ресурсов
        resources = state.fbos
        resources["DISPLAY"] = display_fbo

        # Для scene pipeline используем размер default viewport
        default_pw, default_ph = default_ctx.rect[2], default_ctx.rect[3]

        for canon, names in alias_groups.items():
            if canon == "DISPLAY":
                for name in names:
                    resources[name] = display_fbo
                continue

            spec = resource_specs_map.get(canon)
            if spec is None:
                for name in names:
                    if name in resource_specs_map:
                        spec = resource_specs_map[name]
                        break

            resource_type = "fbo"
            if spec is not None:
                resource_type = spec.resource_type

            if resource_type == "shadow_map_array":
                resolution = 1024
                if spec is not None and spec.size is not None:
                    resolution = spec.size[0]
                shadow_array = state.get_shadow_map_array(canon)
                if shadow_array is None or shadow_array.resolution != resolution:
                    shadow_array = ShadowMapArrayResource(resolution=resolution)
                    state.set_shadow_map_array(canon, shadow_array)
                for name in names:
                    resources[name] = shadow_array
                continue

            if resource_type != "fbo":
                for name in names:
                    if name not in resources:
                        resources[name] = None
                continue

            resource_size = (default_pw, default_ph)
            resource_samples = 1
            resource_format = ""
            if spec is not None:
                if spec.size is not None:
                    resource_size = spec.size
                resource_samples = spec.samples
                if spec.format is not None:
                    resource_format = spec.format

            fb = self._ensure_fbo(state, canon, resource_size, resource_samples, resource_format)
            for name in names:
                resources[name] = fb

        # Очистка ресурсов согласно ResourceSpec
        for resource_name, spec in resource_specs_map.items():
            if spec.resource_type != "fbo":
                continue
            if spec.clear_color is None and spec.clear_depth is None:
                continue
            fb = resources.get(resource_name)
            if fb is None:
                continue
            self.graphics.bind_framebuffer(fb)
            fb_size = spec.size if spec.size is not None else (default_pw, default_ph)
            self.graphics.set_viewport(0, 0, fb_size[0], fb_size[1])
            if spec.clear_color is not None and spec.clear_depth is not None:
                self.graphics.clear_color_depth(spec.clear_color)
            elif spec.clear_color is not None:
                self.graphics.clear_color(spec.clear_color)
            elif spec.clear_depth is not None:
                self.graphics.clear_depth(spec.clear_depth)

        # Выполняем пассы
        lights = scene.build_lights()

        from termin.core.profiler import Profiler
        profiler = Profiler.instance()

        for render_pass in schedule:
            self.graphics.reset_state()
            self._clear_gl_errors()

            # Определяем viewport context для этого pass'а
            pass_viewport_name = render_pass.viewport_name if render_pass.viewport_name else default_viewport
            ctx = viewport_contexts.get(pass_viewport_name, default_ctx)

            px, py, pw, ph = ctx.rect

            pass_reads = {name: resources.get(name) for name in render_pass.reads}
            pass_writes = {name: resources.get(name) for name in render_pass.writes}

            exec_ctx = ExecuteContext(
                graphics=self.graphics,
                reads_fbos=pass_reads,
                writes_fbos=pass_writes,
                rect=(px, py, pw, ph),
                scene=scene,
                camera=ctx.camera,
                context_key=context_key,
                lights=lights,
                canvas=ctx.canvas,
                layer_mask=ctx.layer_mask,
            )

            with profiler.section(render_pass.pass_name):
                render_pass.execute(exec_ctx)

            self._check_gl_errors(render_pass.pass_name)

            for name in render_pass.writes:
                if name in pass_writes and pass_writes[name] is not None:
                    resources[name] = pass_writes[name]

    def _clear_gl_errors(self) -> None:
        """Очищает все pending GL ошибки."""
        import OpenGL.GL as gl
        while gl.glGetError() != gl.GL_NO_ERROR:
            pass

    def _check_gl_errors(self, pass_name: str) -> None:
        """Проверяет и логирует GL ошибки после выполнения пасса."""
        import OpenGL.GL as gl
        from termin._native import log

        GL_ERROR_NAMES = {
            gl.GL_INVALID_ENUM: "GL_INVALID_ENUM",
            gl.GL_INVALID_VALUE: "GL_INVALID_VALUE",
            gl.GL_INVALID_OPERATION: "GL_INVALID_OPERATION",
            gl.GL_STACK_OVERFLOW: "GL_STACK_OVERFLOW",
            gl.GL_STACK_UNDERFLOW: "GL_STACK_UNDERFLOW",
            gl.GL_OUT_OF_MEMORY: "GL_OUT_OF_MEMORY",
            gl.GL_INVALID_FRAMEBUFFER_OPERATION: "GL_INVALID_FRAMEBUFFER_OPERATION",
        }

        while True:
            err = gl.glGetError()
            if err == gl.GL_NO_ERROR:
                break
            error_key = f"{pass_name}:{err}"
            if error_key not in self._logged_errors:
                self._logged_errors.add(error_key)
                error_name = GL_ERROR_NAMES.get(err, f"UNKNOWN(0x{err:x})")
                # Get current GL state for debugging
                current_fbo = gl.glGetIntegerv(gl.GL_FRAMEBUFFER_BINDING)
                current_program = gl.glGetIntegerv(gl.GL_CURRENT_PROGRAM)
                current_vao = gl.glGetIntegerv(gl.GL_VERTEX_ARRAY_BINDING)
                log.error(
                    f"GL error {error_name} (0x{err:x}) after pass '{pass_name}' "
                    f"[FBO={current_fbo}, program={current_program}, VAO={current_vao}]"
                )

    def _ensure_fbo(
        self,
        state: "ViewportRenderState",
        key: str,
        size: Tuple[int, int],
        samples: int = 1,
        format: str = "",
    ) -> "FramebufferHandle":
        """
        Получает или создаёт FBO для ресурса.

        Параметры:
            state: ViewportRenderState с FBO пулом.
            key: Имя ресурса.
            size: Требуемый размер (width, height).
            samples: Количество MSAA samples (1 = без MSAA).
            format: Формат текстуры ("r16f", "r32f", "rgba16f", "rgba32f", "" = rgba8).

        Возвращает:
            FramebufferHandle подходящего размера.
        """
        framebuffer = state.fbos.get(key)
        if framebuffer is None:
            framebuffer = self.graphics.create_framebuffer(size, samples=samples, format=format)
            state.fbos[key] = framebuffer
        else:
            # TODO: пересоздать FBO если изменился samples или format
            framebuffer.resize(size)
        return framebuffer

    # --- Offscreen rendering methods ---

    def render_view_to_fbo(
        self,
        view: "RenderView",
        state: "ViewportRenderState",
        target_fbo: "FramebufferHandle",
        size: Tuple[int, int],
        context_key: int,
    ) -> None:
        """
        Рендерит view в указанный FBO (offscreen).

        Используется для рендера unmanaged viewports в их output_fbo.

        Параметры:
            view: RenderView (сцена, камера, pipeline).
            state: ViewportRenderState (fbos).
            target_fbo: Целевой FBO для рендера.
            size: Размер FBO (width, height).
            context_key: Ключ контекста для кэширования.
        """
        from termin.visualization.render.framegraph import FrameGraph, RenderFramePass

        pipeline = view.pipeline
        if pipeline is None:
            return

        frame_passes = pipeline.passes
        if not frame_passes:
            return

        pw, ph = size

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

        # Собираем ResourceSpecs
        resource_specs_map = {}
        for render_pass in frame_passes:
            for spec in render_pass.get_resource_specs():
                resource_specs_map[spec.resource] = spec
        if pipeline.pipeline_specs:
            for spec in pipeline.pipeline_specs:
                resource_specs_map[spec.resource] = spec

        # Управляем пулом ресурсов
        resources = state.fbos
        # OUTPUT = target_fbo (вместо DISPLAY)
        resources["OUTPUT"] = target_fbo
        resources["DISPLAY"] = target_fbo  # Для совместимости со старыми пайплайнами

        for canon, names in alias_groups.items():
            if canon in ("DISPLAY", "OUTPUT"):
                for name in names:
                    resources[name] = target_fbo
                continue

            spec = resource_specs_map.get(canon)
            if spec is None:
                for name in names:
                    if name in resource_specs_map:
                        spec = resource_specs_map[name]
                        break

            resource_type = "fbo"
            if spec is not None:
                resource_type = spec.resource_type

            if resource_type == "shadow_map_array":
                resolution = 1024
                if spec is not None and spec.size is not None:
                    resolution = spec.size[0]
                shadow_array = state.get_shadow_map_array(canon)
                if shadow_array is None or shadow_array.resolution != resolution:
                    shadow_array = ShadowMapArrayResource(resolution=resolution)
                    state.set_shadow_map_array(canon, shadow_array)
                for name in names:
                    resources[name] = shadow_array
                continue

            if resource_type != "fbo":
                for name in names:
                    if name not in resources:
                        resources[name] = None
                continue

            resource_size = (pw, ph)
            resource_samples = 1
            resource_format = ""
            if spec is not None:
                if spec.size is not None:
                    resource_size = spec.size
                resource_samples = spec.samples
                if spec.format is not None:
                    resource_format = spec.format

            fb = self._ensure_fbo(state, canon, resource_size, resource_samples, resource_format)
            for name in names:
                resources[name] = fb

        # Очистка ресурсов согласно ResourceSpec
        for resource_name, spec in resource_specs_map.items():
            if spec.resource_type != "fbo":
                continue
            if spec.clear_color is None and spec.clear_depth is None:
                continue
            fb = resources.get(resource_name)
            if fb is None:
                continue
            self.graphics.bind_framebuffer(fb)
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

        from termin.core.profiler import Profiler
        profiler = Profiler.instance()

        for render_pass in schedule:
            self.graphics.reset_state()
            self._clear_gl_errors()

            pass_reads = {name: resources.get(name) for name in render_pass.reads}
            pass_writes = {name: resources.get(name) for name in render_pass.writes}

            ctx = ExecuteContext(
                graphics=self.graphics,
                reads_fbos=pass_reads,
                writes_fbos=pass_writes,
                rect=(0, 0, pw, ph),
                scene=scene,
                camera=view.camera,
                context_key=context_key,
                lights=lights,
                canvas=view.canvas,
                layer_mask=view.layer_mask,
            )

            with profiler.section(render_pass.pass_name):
                render_pass.execute(ctx)

            self._check_gl_errors(render_pass.pass_name)

            for name in render_pass.writes:
                if name in pass_writes and pass_writes[name] is not None:
                    resources[name] = pass_writes[name]

    def render_scene_pipeline_offscreen(
        self,
        pipeline: "RenderPipeline",
        scene: "Scene",
        viewport_contexts: Dict[str, ViewportContext],
        shared_state: "ViewportRenderState",
        context_key: int,
        default_viewport: str = "",
    ) -> None:
        """
        Выполняет scene pipeline, рендеря каждый viewport в его output_fbo.

        Каждый pass выбирает viewport_context по viewport_name.
        Финальный результат каждого viewport идёт в его output_fbo.

        Параметры:
            pipeline: Pipeline для выполнения.
            scene: Сцена.
            viewport_contexts: Словарь viewport_name -> ViewportContext (с output_fbo).
            shared_state: ViewportRenderState с общими ресурсами.
            context_key: Ключ контекста.
            default_viewport: Viewport по умолчанию для пассов без viewport_name.
        """
        from termin.visualization.render.framegraph import FrameGraph, RenderFramePass
        from termin._native import log

        frame_passes = pipeline.passes
        if not frame_passes:
            return

        # Выбираем первый доступный viewport как default
        if not default_viewport and viewport_contexts:
            default_viewport = next(iter(viewport_contexts.keys()))

        default_ctx = viewport_contexts.get(default_viewport)
        if default_ctx is None and viewport_contexts:
            default_ctx = next(iter(viewport_contexts.values()))

        if default_ctx is None:
            log.error("[render_scene_pipeline_offscreen] No viewport contexts provided")
            return

        # Обновляем aspect ratio для всех камер
        for ctx in viewport_contexts.values():
            px, py, pw, ph = ctx.rect
            ctx.camera.set_aspect(pw / float(max(1, ph)))

        # Запрашиваем required_resources
        for render_pass in frame_passes:
            if isinstance(render_pass, RenderFramePass):
                render_pass.required_resources()

        # Строим framegraph
        graph = FrameGraph(frame_passes)
        schedule = graph.build_schedule()
        alias_groups = graph.fbo_alias_groups()

        # Собираем ResourceSpecs
        resource_specs_map = {}
        for render_pass in frame_passes:
            for spec in render_pass.get_resource_specs():
                resource_specs_map[spec.resource] = spec
        if pipeline.pipeline_specs:
            for spec in pipeline.pipeline_specs:
                resource_specs_map[spec.resource] = spec

        # Управляем пулом ресурсов
        resources = shared_state.fbos

        # Для scene pipeline используем размер default viewport
        default_pw, default_ph = default_ctx.rect[2], default_ctx.rect[3]

        # OUTPUT/DISPLAY = default viewport's output_fbo
        if default_ctx.output_fbo is not None:
            resources["OUTPUT"] = default_ctx.output_fbo
            resources["DISPLAY"] = default_ctx.output_fbo

        for canon, names in alias_groups.items():
            if canon in ("DISPLAY", "OUTPUT"):
                target_fbo = default_ctx.output_fbo if default_ctx.output_fbo else None
                for name in names:
                    resources[name] = target_fbo
                continue

            spec = resource_specs_map.get(canon)
            if spec is None:
                for name in names:
                    if name in resource_specs_map:
                        spec = resource_specs_map[name]
                        break

            resource_type = "fbo"
            if spec is not None:
                resource_type = spec.resource_type

            if resource_type == "shadow_map_array":
                resolution = 1024
                if spec is not None and spec.size is not None:
                    resolution = spec.size[0]
                shadow_array = shared_state.get_shadow_map_array(canon)
                if shadow_array is None or shadow_array.resolution != resolution:
                    shadow_array = ShadowMapArrayResource(resolution=resolution)
                    shared_state.set_shadow_map_array(canon, shadow_array)
                for name in names:
                    resources[name] = shadow_array
                continue

            if resource_type != "fbo":
                for name in names:
                    if name not in resources:
                        resources[name] = None
                continue

            resource_size = (default_pw, default_ph)
            resource_samples = 1
            resource_format = ""
            if spec is not None:
                if spec.size is not None:
                    resource_size = spec.size
                resource_samples = spec.samples
                if spec.format is not None:
                    resource_format = spec.format

            fb = self._ensure_fbo(shared_state, canon, resource_size, resource_samples, resource_format)
            for name in names:
                resources[name] = fb

        # Очистка ресурсов
        for resource_name, spec in resource_specs_map.items():
            if spec.resource_type != "fbo":
                continue
            if spec.clear_color is None and spec.clear_depth is None:
                continue
            fb = resources.get(resource_name)
            if fb is None:
                continue
            self.graphics.bind_framebuffer(fb)
            fb_size = spec.size if spec.size is not None else (default_pw, default_ph)
            self.graphics.set_viewport(0, 0, fb_size[0], fb_size[1])
            if spec.clear_color is not None and spec.clear_depth is not None:
                self.graphics.clear_color_depth(spec.clear_color)
            elif spec.clear_color is not None:
                self.graphics.clear_color(spec.clear_color)
            elif spec.clear_depth is not None:
                self.graphics.clear_depth(spec.clear_depth)

        # Выполняем пассы
        lights = scene.build_lights()

        from termin.core.profiler import Profiler
        profiler = Profiler.instance()

        for render_pass in schedule:
            self.graphics.reset_state()
            self._clear_gl_errors()

            # Определяем viewport context для этого pass'а
            pass_viewport_name = render_pass.viewport_name if render_pass.viewport_name else default_viewport
            ctx = viewport_contexts.get(pass_viewport_name, default_ctx)

            px, py, pw, ph = ctx.rect

            # Если pass пишет в OUTPUT/DISPLAY, используем output_fbo этого viewport
            pass_writes_dict = {name: resources.get(name) for name in render_pass.writes}
            if ctx.output_fbo is not None:
                for write_name in render_pass.writes:
                    if write_name in ("OUTPUT", "DISPLAY"):
                        pass_writes_dict[write_name] = ctx.output_fbo

            pass_reads = {name: resources.get(name) for name in render_pass.reads}

            exec_ctx = ExecuteContext(
                graphics=self.graphics,
                reads_fbos=pass_reads,
                writes_fbos=pass_writes_dict,
                rect=(px, py, pw, ph),
                scene=scene,
                camera=ctx.camera,
                context_key=context_key,
                lights=lights,
                canvas=ctx.canvas,
                layer_mask=ctx.layer_mask,
            )

            with profiler.section(render_pass.pass_name):
                render_pass.execute(exec_ctx)

            self._check_gl_errors(render_pass.pass_name)

            for name in render_pass.writes:
                if name in pass_writes_dict and pass_writes_dict[name] is not None:
                    resources[name] = pass_writes_dict[name]
