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

# Import to ensure GLSL preprocessor fallback loader is set up before any shader compilation
import termin.visualization.render.glsl_preprocessor  # noqa: F401

# Import tc_frame_graph functions for C-based scheduling
try:
    from termin._native.render import (
        tc_frame_graph_build,
        tc_frame_graph_destroy,
        tc_frame_graph_get_error,
        tc_frame_graph_get_error_message,
        tc_frame_graph_get_schedule,
        tc_frame_graph_get_alias_groups,
        tc_resources_allocate_dict,
        TcFrameGraphError,
        RenderEngine as CppRenderEngine,
        ViewportContext as CppViewportContext,
        Rect4i,
    )
except ImportError as e:
    raise ImportError(f"tc_frame_graph bindings required: {e}") from e


def _build_schedule_from_pipeline(pipeline: "RenderPipeline", frame_passes):
    """
    Build pass schedule and alias_groups using tc_frame_graph.

    Returns: (schedule, alias_groups)
    """
    from termin._native import log

    tc_pipeline = pipeline._tc_pipeline

    if tc_pipeline.pass_count != len(frame_passes):
        py_names = [p.pass_name for p in frame_passes]
        for p in frame_passes:
            has_tc = p._tc_pass is not None
            log.error(f"[engine]   '{p.pass_name}' ({type(p).__name__}): _tc_pass={'set' if has_tc else 'None'}")
        raise RuntimeError(
            f"tc_pipeline.pass_count={tc_pipeline.pass_count} != len(frame_passes)={len(frame_passes)}"
        )

    fg = tc_frame_graph_build(tc_pipeline)
    try:
        error = tc_frame_graph_get_error(fg)
        if error != TcFrameGraphError.OK:
            msg = tc_frame_graph_get_error_message(fg)
            raise RuntimeError(f"tc_frame_graph error: {msg}")

        # Get schedule from C frame graph
        tc_schedule = tc_frame_graph_get_schedule(fg)
        pass_map = {p.pass_name: p for p in frame_passes}
        schedule = []
        for tc_pass in tc_schedule:
            py_pass = pass_map.get(tc_pass.pass_name)
            if py_pass is not None:
                schedule.append(py_pass)

        if len(schedule) != len(frame_passes):
            log.error(f"[engine] pass_map keys: {list(pass_map.keys())}")
            tc_names = [tc_pass.pass_name for tc_pass in tc_schedule]
            log.error(f"[engine] tc_schedule names: {tc_names}")
            missing = set(pass_map.keys()) - set(tc_names)
            log.error(f"[engine] missing from tc_schedule: {missing}")
            raise RuntimeError(
                f"tc_frame_graph schedule mismatch: got {len(schedule)}, expected {len(frame_passes)}"
            )

        # Get alias_groups from C frame graph
        c_alias_groups = tc_frame_graph_get_alias_groups(fg)
        alias_groups = {k: set(v) for k, v in c_alias_groups.items()}
        return schedule, alias_groups
    finally:
        tc_frame_graph_destroy(fg)


def _allocate_pipeline_resources(
    engine: "RenderEngine",
    state: "ViewportRenderState",
    alias_groups: Dict[str, Any],
    resource_specs_map: Dict[str, Any],
    target_fbo: "FramebufferHandle",
    size: Tuple[int, int],
) -> Dict[str, Any]:
    """
    Allocate FBOs and other resources based on alias_groups.

    Returns dict mapping resource names to FBO handles (or other resource objects).
    """
    pw, ph = size
    resources = state.fbos

    # OUTPUT/DISPLAY point to target
    resources["OUTPUT"] = target_fbo
    resources["DISPLAY"] = target_fbo

    for canon, names in alias_groups.items():
        # Skip DISPLAY/OUTPUT - already set
        if canon in ("DISPLAY", "OUTPUT"):
            for name in names:
                resources[name] = target_fbo
            continue

        # Find spec for this canonical resource
        spec = resource_specs_map.get(canon)
        if spec is None:
            for name in names:
                if name in resource_specs_map:
                    spec = resource_specs_map[name]
                    break

        resource_type = spec.resource_type if spec else "fbo"

        # Handle shadow_map_array
        if resource_type == "shadow_map_array":
            resolution = spec.size[0] if spec and spec.size else 1024
            shadow_array = state.get_shadow_map_array(canon)
            if shadow_array is None or shadow_array.resolution != resolution:
                shadow_array = ShadowMapArrayResource(resolution=resolution)
                state.set_shadow_map_array(canon, shadow_array)
            for name in names:
                resources[name] = shadow_array
            continue

        # Skip unknown resource types
        if resource_type != "fbo":
            for name in names:
                if name not in resources:
                    resources[name] = None
            continue

        # FBO resource - determine size/samples/format
        resource_size = (pw, ph)
        resource_samples = 1
        resource_format = ""
        if spec:
            if spec.size:
                resource_size = spec.size
            resource_samples = spec.samples
            if spec.format:
                resource_format = spec.format

        fb = engine._ensure_fbo(state, canon, resource_size, resource_samples, resource_format)
        for name in names:
            resources[name] = fb

    return resources


def _clear_resources_by_spec(
    graphics: "GraphicsBackend",
    resources: Dict[str, Any],
    resource_specs_map: Dict[str, Any],
    default_size: Tuple[int, int],
) -> None:
    """Clear FBO resources according to their specs."""
    pw, ph = default_size
    for resource_name, spec in resource_specs_map.items():
        if spec.resource_type != "fbo":
            continue
        if spec.clear_color is None and spec.clear_depth is None:
            continue
        fb = resources.get(resource_name)
        if fb is None:
            continue

        graphics.bind_framebuffer(fb)
        fb_size = spec.size if spec.size else (pw, ph)
        graphics.set_viewport(0, 0, fb_size[0], fb_size[1])

        if spec.clear_color is not None and spec.clear_depth is not None:
            graphics.clear_color_depth(spec.clear_color)
        elif spec.clear_color is not None:
            graphics.clear_color(spec.clear_color)
        elif spec.clear_depth is not None:
            graphics.clear_depth(spec.clear_depth)

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
        self._cpp_engine = CppRenderEngine(graphics)  # C++ render engine

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

        Параметры:
            surface: Целевая поверхность рендеринга.
            views: Итератор пар (RenderView, ViewportRenderState).
            present: Вызывать ли surface.present() после рендера.
        """
        from termin.core.profiler import Profiler
        from termin._native import log

        profiler = Profiler.instance()

        with profiler.section("Render"):
            self.graphics.ensure_ready()
            surface.make_current()

            width, height = surface.get_size()
            display_fbo = surface.get_framebuffer()

            # Регистрируем контекст для корректного удаления GPU ресурсов
            from termin.visualization.platform.backends import register_context
            register_context(surface.make_current)

            for view, state in views:
                try:
                    self.render_view_to_fbo(
                        view=view,
                        state=state,
                        target_fbo=display_fbo,
                        size=(width, height),
                    )
                except Exception as e:
                    import traceback
                    tb = traceback.format_exc()
                    log.error(f"Pipeline error: {e}\n{tb}")

            if present:
                surface.present()

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
    ) -> None:
        """
        Рендерит view в указанный FBO (offscreen).

        Используется для рендера unmanaged viewports в их output_fbo.
        Использует C++ RenderEngine для выполнения рендеринга.

        Параметры:
            view: RenderView (сцена, камера, pipeline).
            state: ViewportRenderState (fbos).
            target_fbo: Целевой FBO для рендера.
            size: Размер FBO (width, height).
        """
        from termin._native import log

        pipeline = view.pipeline
        if pipeline is None:
            log.warn("[engine] render_view_to_fbo: pipeline is None")
            return

        if not pipeline.passes:
            log.warn(f"[engine] render_view_to_fbo: no passes in '{pipeline.name}'")
            return

        scene = view.scene
        if scene is None or scene.is_destroyed:
            log.warn("[engine] render_view_to_fbo: scene is None or destroyed")
            return

        from termin.core.profiler import Profiler
        profiler = Profiler.instance()

        pw, ph = size

        # Обновляем aspect ratio камеры
        view.camera.set_aspect(pw / float(max(1, ph)))

        # Строим lights
        with profiler.section("Build Lights"):
            lights = scene.build_lights()

        # Вызываем C++ RenderEngine
        with profiler.section("C++ Render Pipeline"):
            self._cpp_engine.render_view_to_fbo(
                pipeline,
                target_fbo,
                pw,
                ph,
                scene._tc_scene.scene_ref(),
                view.camera,
                view.viewport,
                lights,
                view.layer_mask,
            )

    def render_scene_pipeline_offscreen(
        self,
        pipeline: "RenderPipeline",
        scene: "Scene",
        viewport_contexts: Dict[str, ViewportContext],
        shared_state: "ViewportRenderState",
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
            default_viewport: Viewport по умолчанию для пассов без viewport_name.
        """
        from termin.visualization.render.framegraph import RenderFramePass
        from termin._native import log

        frame_passes = pipeline.passes
        if not frame_passes:
            return

        if scene.is_destroyed:
            return

        if not viewport_contexts:
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

        # Build lights
        lights = scene.build_lights()

        # Convert Python ViewportContext to C++ ViewportContext
        cpp_viewport_contexts: Dict[str, CppViewportContext] = {}
        for name, ctx in viewport_contexts.items():
            cpp_ctx = CppViewportContext()
            cpp_ctx.name = name
            cpp_ctx.camera = ctx.camera
            px, py, pw, ph = ctx.rect
            cpp_ctx.rect = Rect4i(px, py, pw, ph)
            cpp_ctx.layer_mask = ctx.layer_mask
            cpp_ctx.output_fbo = ctx.output_fbo
            cpp_viewport_contexts[name] = cpp_ctx

        # Execute via C++ RenderEngine
        self._cpp_engine.render_scene_pipeline_offscreen(
            pipeline,
            scene._tc_scene.scene_ref(),
            cpp_viewport_contexts,
            lights,
            default_viewport,
        )
