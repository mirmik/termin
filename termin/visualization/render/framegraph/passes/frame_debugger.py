"""
FrameDebuggerPass — пасс для захвата промежуточного состояния framegraph.

Блитит выбранный ресурс прямо в окно дебаггера и читает depth buffer.
"""
from __future__ import annotations

from typing import Set, TYPE_CHECKING, Any, Callable

from termin.visualization.render.framegraph.passes.base import RenderFramePass

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle
    from termin.visualization.render.framegraph.execute_context import ExecuteContext


class FrameDebuggerPass(RenderFramePass):
    """
    Пасс для режима "между пассами" в framegraph debugger.

    Блитит выбранный ресурс прямо в SDL окно дебаггера
    и читает depth buffer через callback.
    """

    category = "Debug"

    node_inputs = [("input_res", "fbo")]
    node_outputs = []  # Output is debug window

    _shader = None

    @staticmethod
    def _get_shader():
        """Возвращает шейдер с поддержкой HDR highlight и channel modes."""
        if FrameDebuggerPass._shader is not None:
            return FrameDebuggerPass._shader

        from termin.visualization.render.shader import ShaderProgram

        vert_src = """
        #version 330 core
        layout(location = 0) in vec2 a_pos;
        layout(location = 1) in vec2 a_uv;
        out vec2 v_uv;
        void main() {
            v_uv = a_uv;
            gl_Position = vec4(a_pos, 0.0, 1.0);
        }
        """
        frag_src = """
        #version 330 core
        in vec2 v_uv;
        uniform sampler2D u_tex;
        uniform int u_channel;  // 0=RGB, 1=R, 2=G, 3=B, 4=A
        uniform int u_highlight_hdr;  // 1=highlight pixels > 1.0
        out vec4 FragColor;
        void main() {
            vec4 c = texture(u_tex, v_uv);
            vec3 result;

            if (u_channel == 1) {
                result = vec3(c.r);
            } else if (u_channel == 2) {
                result = vec3(c.g);
            } else if (u_channel == 3) {
                result = vec3(c.b);
            } else if (u_channel == 4) {
                result = vec3(c.a);
            } else {
                result = c.rgb;
            }

            // HDR highlight: show pixels > 1.0 with magenta overlay
            if (u_highlight_hdr == 1) {
                float maxVal = max(max(c.r, c.g), c.b);
                if (maxVal > 1.0) {
                    float intensity = clamp((maxVal - 1.0) / 2.0, 0.0, 1.0);
                    result = mix(result, vec3(1.0, 0.0, 1.0), 0.5 + intensity * 0.5);
                }
            }

            FragColor = vec4(result, 1.0);
        }
        """
        FrameDebuggerPass._shader = ShaderProgram(vert_src, frag_src)
        return FrameDebuggerPass._shader

    def __init__(
        self,
        get_source_res: Callable[[], str | None] | None = None,
        pass_name: str = "FrameDebugger",
    ):
        super().__init__(pass_name=pass_name)
        self._get_source_res = get_source_res
        self._current_src_name: str | None = None

        # SDL окно дебаггера и callback для depth
        self._debugger_window: Any = None
        self._depth_callback: Callable[[Any], None] | None = None
        self._depth_error_callback: Callable[[str], None] | None = None

        # Флаг запроса обновления depth buffer (только по кнопке)
        self._depth_update_requested: bool = False

        # Временный FBO для resolve MSAA (создаётся при необходимости)
        self._resolve_fbo: "FramebufferHandle | None" = None
        self._resolve_fbo_size: tuple[int, int] = (0, 0)

        # HDR highlight mode
        self._highlight_hdr: bool = False
        self._channel_mode: int = 0  # 0=RGB, 1=R, 2=G, 3=B, 4=A

    def compute_reads(self) -> Set[str]:
        if self._get_source_res is None:
            return set()
        src_name = self._get_source_res()
        if src_name:
            self._current_src_name = src_name
            return {src_name}
        self._current_src_name = None
        return set()

    def compute_writes(self) -> Set[str]:
        return set()

    def request_depth_update(self) -> None:
        """Запросить обновление depth buffer на следующем кадре."""
        self._depth_update_requested = True

    def set_highlight_hdr(self, enabled: bool) -> None:
        """Включает/выключает подсветку HDR пикселей."""
        self._highlight_hdr = enabled

    def set_channel_mode(self, mode: int) -> None:
        """Устанавливает режим отображения каналов (0=RGB, 1=R, 2=G, 3=B, 4=A)."""
        self._channel_mode = mode

    def set_debugger_window(
        self,
        window,
        depth_callback: Callable[[Any], None] | None = None,
        depth_error_callback: Callable[[str], None] | None = None,
    ) -> None:
        """
        Устанавливает SDL окно дебаггера для блита.

        Args:
            window: SDL окно дебаггера. None — отключить.
            depth_callback: Callback для передачи depth buffer (numpy array).
            depth_error_callback: Callback для сообщения об ошибке чтения depth.
        """
        self._debugger_window = window
        self._depth_callback = depth_callback
        self._depth_error_callback = depth_error_callback

    def required_resources(self) -> set[str]:
        """Динамически определяет читаемые ресурсы."""
        return set(self.reads)

    def _report_depth_error(self, message: str) -> None:
        """Сообщает об ошибке чтения depth buffer."""
        if self._depth_error_callback is not None:
            self._depth_error_callback(message)

    def _read_depth_buffer(self, graphics: "GraphicsBackend", fbo: "FramebufferHandle") -> None:
        """Читает depth buffer и вызывает соответствующий callback.

        Args:
            graphics: Бэкенд графики.
            fbo: FramebufferHandle для чтения (должен быть non-MSAA, после резолва).
        """
        if fbo is None:
            self._report_depth_error("FBO не найден")
            return

        # Пытаемся прочитать depth
        depth = graphics.read_depth_buffer(fbo)
        if depth is None:
            self._report_depth_error("read_depth_buffer вернул None")
            return

        if self._depth_callback is not None:
            self._depth_callback(depth)

    def _get_or_create_resolve_fbo(
        self, graphics: "GraphicsBackend", width: int, height: int
    ) -> "FramebufferHandle":
        """Возвращает FBO для resolve MSAA, создаёт при необходимости."""
        if (
            self._resolve_fbo is not None
            and self._resolve_fbo_size == (width, height)
        ):
            return self._resolve_fbo

        # Создаём новый FBO нужного размера с float форматом для сохранения HDR
        self._resolve_fbo = graphics.create_framebuffer(width, height, samples=1, format="rgba16f")
        self._resolve_fbo_size = (width, height)
        return self._resolve_fbo

    def _get_fbo_from_resource(self, resource) -> "FramebufferHandle | None":
        """Извлекает FramebufferHandle из ресурса."""
        from termin.visualization.render.framegraph.resource import (
            SingleFBO,
            ShadowMapArrayResource,
        )
        from termin.graphics import FramebufferHandle

        if isinstance(resource, ShadowMapArrayResource):
            if len(resource) == 0:
                return None
            return resource[0].fbo

        if isinstance(resource, SingleFBO):
            return resource._fbo

        if isinstance(resource, FramebufferHandle):
            return resource

        return None

    def _get_texture_from_resource(self, resource, shadow_map_index: int = 0):
        """
        Извлекает текстуру из ресурса framegraph для отображения.

        Поддерживает:
        - SingleFBO: возвращает color_texture()
        - ShadowMapArrayResource: возвращает текстуру из первого entry (или по индексу)
        - FramebufferHandle (C++): возвращает color_texture()

        Args:
            resource: объект ресурса (SingleFBO, ShadowMapArrayResource, FramebufferHandle)
            shadow_map_index: индекс shadow map для ShadowMapArrayResource

        Returns:
            GPUTextureHandle или None
        """
        if resource is None:
            return None

        from termin.visualization.render.framegraph.resource import (
            SingleFBO,
            ShadowMapArrayResource,
        )
        from termin.graphics import FramebufferHandle

        if isinstance(resource, ShadowMapArrayResource):
            if len(resource) == 0:
                return None
            index = min(shadow_map_index, len(resource) - 1)
            entry = resource[index]
            return entry.texture()

        if isinstance(resource, SingleFBO):
            return resource.color_texture()

        if isinstance(resource, FramebufferHandle):
            return resource.color_texture()

        return None

    def execute(self, ctx: "ExecuteContext") -> None:
        # Если нет окна дебаггера — ничего не делаем
        if self._debugger_window is None:
            return

        if self._get_source_res is None:
            return

        src_name = self._get_source_res()
        if not src_name:
            return

        src_fb = ctx.reads_fbos.get(src_name)
        if src_fb is None:
            return

        from sdl2 import video as sdl_video

        # Получаем FBO из ресурса
        fbo = self._get_fbo_from_resource(src_fb)
        if fbo is None:
            return

        # Проверяем, нужен ли resolve для MSAA
        texture_fbo = fbo
        if fbo.is_msaa():
            # Создаём или переиспользуем resolve FBO
            w, h = fbo.get_size()
            resolve_fbo = self._get_or_create_resolve_fbo(ctx.graphics, w, h)
            # Blit MSAA -> non-MSAA (color + depth)
            ctx.graphics.blit_framebuffer(
                fbo, resolve_fbo,
                (0, 0, w, h),
                (0, 0, w, h),
                blit_color=True,
                blit_depth=True,
            )
            texture_fbo = resolve_fbo

        # Читаем depth buffer только по запросу (после резолва, если был MSAA)
        if self._depth_update_requested:
            self._depth_update_requested = False
            self._read_depth_buffer(ctx.graphics, texture_fbo)

        # Извлекаем текстуру из (возможно resolved) FBO
        tex = texture_fbo.color_texture()
        if tex is None:
            return

        try:
            # Запоминаем текущий контекст и окно
            saved_context = sdl_video.SDL_GL_GetCurrentContext()
            saved_window = sdl_video.SDL_GL_GetCurrentWindow()

            # Переключаемся на контекст окна дебаггера
            self._debugger_window.make_current()

            # Получаем размер окна
            dst_w, dst_h = self._debugger_window.framebuffer_size()

            # Биндим framebuffer 0 (окно)
            ctx.graphics.bind_framebuffer(None)
            ctx.graphics.set_viewport(0, 0, dst_w, dst_h)

            # Clear для debug
            ctx.graphics.clear_color(0.2, 0.0, 0.0, 1.0)

            ctx.graphics.set_depth_test(False)
            ctx.graphics.set_depth_mask(False)

            # Рендерим fullscreen quad с нашим шейдером
            shader = FrameDebuggerPass._get_shader()
            shader.ensure_ready(ctx.graphics, 0)  # debugger has its own context
            shader.use()
            shader.set_uniform_int("u_tex", 0)
            shader.set_uniform_int("u_channel", self._channel_mode)
            shader.set_uniform_int("u_highlight_hdr", 1 if self._highlight_hdr else 0)
            tex.bind(0)
            ctx.graphics.draw_ui_textured_quad(0)

            ctx.graphics.set_depth_test(True)
            ctx.graphics.set_depth_mask(True)

            # Показываем результат
            self._debugger_window.swap_buffers()

        except Exception as e:
            from termin._native import log
            log.error(f"[FrameDebuggerPass] blit failed: {e}")

        finally:
            # Восстанавливаем исходный контекст
            if saved_window and saved_context:
                sdl_video.SDL_GL_MakeCurrent(saved_window, saved_context)
