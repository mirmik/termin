"""
FrameDebuggerPass — пасс для захвата промежуточного состояния framegraph.

Блитит выбранный ресурс прямо в окно дебаггера и читает depth buffer.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from termin.visualization.render.framegraph.passes.base import RenderFramePass

if TYPE_CHECKING:
    from termin.visualization.platform.backends.base import GraphicsBackend, FramebufferHandle


class FrameDebuggerPass(RenderFramePass):
    """
    Пасс для режима "между пассами" в framegraph debugger.

    Блитит выбранный ресурс прямо в SDL окно дебаггера
    и читает depth buffer через callback.
    """

    def __init__(
        self,
        get_source_res: Callable[[], str | None] | None = None,
        pass_name: str = "FrameDebugger",
    ):
        super().__init__(
            pass_name=pass_name,
            reads=set(),
            writes=set(),
        )
        self._get_source_res = get_source_res
        self._current_src_name: str | None = None

        # SDL окно дебаггера и callback для depth
        self._debugger_window: Any = None
        self._depth_callback: Callable[[Any], None] | None = None

    def set_debugger_window(
        self,
        window,
        depth_callback: Callable[[Any], None] | None = None,
    ) -> None:
        """
        Устанавливает SDL окно дебаггера для блита.

        Args:
            window: SDL окно дебаггера. None — отключить.
            depth_callback: Callback для передачи depth buffer (numpy array).
        """
        self._debugger_window = window
        self._depth_callback = depth_callback

    def required_resources(self) -> set[str]:
        """Динамически определяет читаемые ресурсы."""
        if self._get_source_res is None:
            self._current_src_name = None
            self.reads = set()
            return set()

        src_name = self._get_source_res()
        if src_name:
            self._current_src_name = src_name
            self.reads = {src_name}
            return {src_name}
        else:
            self.reads = set()
            self._current_src_name = None
            return set()

    def _serialize_params(self) -> dict:
        return {}

    @classmethod
    def _deserialize_instance(cls, data: dict, resource_manager=None) -> "FrameDebuggerPass":
        return cls(
            get_source_res=None,
            pass_name=data.get("pass_name", "FrameDebugger"),
        )

    def execute(
        self,
        graphics: "GraphicsBackend",
        reads_fbos: dict[str, "FramebufferHandle" | None],
        writes_fbos: dict[str, "FramebufferHandle" | None],
        rect: tuple[int, int, int, int],
        scene=None,
        camera=None,
        context_key: int = 0,
        lights=None,
        canvas=None,
    ):
        # Если нет окна дебаггера — ничего не делаем
        if self._debugger_window is None:
            return

        if self._get_source_res is None:
            return

        src_name = self._get_source_res()
        if not src_name:
            return

        src_fb = reads_fbos.get(src_name)
        if src_fb is None:
            return

        from termin.visualization.render.framegraph.passes.present import (
            PresentToScreenPass,
            _get_texture_from_resource,
        )
        from sdl2 import video as sdl_video

        # Читаем depth buffer до переключения контекста
        if self._depth_callback is not None:
            depth = graphics.read_depth_buffer(src_fb)
            if depth is not None:
                self._depth_callback(depth)

        # Извлекаем текстуру
        tex = _get_texture_from_resource(src_fb)
        if tex is None:
            return

        # Запоминаем текущий контекст и окно
        saved_context = sdl_video.SDL_GL_GetCurrentContext()
        saved_window = sdl_video.SDL_GL_GetCurrentWindow()

        # Переключаемся на контекст окна дебаггера
        self._debugger_window.make_current()

        # Получаем размер окна
        dst_w, dst_h = self._debugger_window.framebuffer_size()

        # Биндим framebuffer 0 (окно)
        graphics.bind_framebuffer(None)
        graphics.set_viewport(0, 0, dst_w, dst_h)

        graphics.set_depth_test(False)
        graphics.set_depth_mask(False)

        # Рендерим fullscreen quad
        shader = PresentToScreenPass._get_shader()
        shader.ensure_ready(graphics)
        shader.use()
        shader.set_uniform_int("u_tex", 0)
        tex.bind(0)
        graphics.draw_ui_textured_quad(0)

        graphics.set_depth_test(True)
        graphics.set_depth_mask(True)

        # Показываем результат
        self._debugger_window.swap_buffers()

        # Восстанавливаем исходный контекст
        if saved_window and saved_context:
            sdl_video.SDL_GL_MakeCurrent(saved_window, saved_context)
