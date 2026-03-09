"""Viewport3D — виджет для отображения 3D-сцены через FBO.

Принимает FBOSurface от FBOWindowBackend. На каждом кадре отображает
содержимое FBO через glBlitFramebuffer в область виджета.
Перенаправляет события мыши и клавиатуры в input manager 3D-движка.

Usage::

    surface = FBOSurface(width=800, height=600)
    display = Display(surface=surface, name="Editor")
    display.connect_input()

    viewport = Viewport3D()
    viewport.set_surface(surface, display)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from tcgui.widgets.widget import Widget
from tcgui.widgets.events import MouseEvent, MouseWheelEvent, KeyEvent

if TYPE_CHECKING:
    from termin.visualization.platform.backends.fbo_backend import FBOSurface


class Viewport3D(Widget):
    """Виджет, отображающий FBO от 3D-движка.

    FBOSurface's FBO lives in the offscreen GL context (where present_display
    writes to it). This widget runs in the main window GL context. Since FBOs
    are per-context objects, we create a local FBO here that wraps the *shared*
    color texture from the surface. Textures are shared between contexts.
    """

    def __init__(self) -> None:
        super().__init__()
        self.focusable = True

        self._surface: FBOSurface | None = None
        self._input_manager_ptr: int = 0

        # Коллбек вызывается при изменении размера (до того как FBO пересоздан)
        self.on_before_resize: Callable[[int, int], None] | None = None

        # Local FBO in main window context wrapping the shared color texture.
        self._local_blit_fbo: int = 0
        self._local_blit_tex: int = 0

    # ------------------------------------------------------------------
    # Подключение
    # ------------------------------------------------------------------

    def set_surface(self, surface: FBOSurface, display=None) -> None:
        """Подключить FBOSurface и опционально Display для получения input manager."""
        self._surface = surface
        if display is not None:
            self._connect_input(display)

    def _connect_input(self, display) -> None:
        """Получить input_manager_ptr от Display."""
        try:
            from termin._native.render import (
                _display_get_surface_ptr,
                _render_surface_get_input_manager,
            )
            surface_ptr = _display_get_surface_ptr(display.tc_display_ptr)
            if surface_ptr:
                ptr = _render_surface_get_input_manager(surface_ptr)
                self._input_manager_ptr = ptr if ptr else 0
            else:
                self._input_manager_ptr = 0
        except Exception as e:
            from tcbase import log
            log.error(f"Viewport3D._connect_input failed: {e}")
            self._input_manager_ptr = 0

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float) -> None:
        old_w = int(self.width)
        old_h = int(self.height)
        super().layout(x, y, width, height, viewport_w, viewport_h)

        new_w = int(width)
        new_h = int(height)

        if self._surface is not None and (new_w != old_w or new_h != old_h):
            if self.on_before_resize is not None:
                self.on_before_resize(new_w, new_h)
            self._surface.resize(new_w, new_h)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self, renderer: 'UIRenderer') -> None:
        if self._surface is None or self._surface.color_texture_id == 0:
            # FBO не готов — заглушка
            renderer.draw_rect(self.x, self.y, self.width, self.height,
                               (0.05, 0.05, 0.05, 1.0))
            return

        self._blit_fbo(renderer)

    def _blit_fbo(self, renderer: 'UIRenderer') -> None:
        from OpenGL.GL import (
            glBindFramebuffer, GL_READ_FRAMEBUFFER, GL_DRAW_FRAMEBUFFER,
            GL_FRAMEBUFFER,
            glBlitFramebuffer, GL_COLOR_BUFFER_BIT, GL_LINEAR,
            glDisable, GL_SCISSOR_TEST,
            glGenFramebuffers, glFramebufferTexture2D,
            GL_TEXTURE_2D, GL_COLOR_ATTACHMENT0,
        )

        tex_id = self._surface.color_texture_id
        fbo_w, fbo_h = self._surface.framebuffer_size()

        # Create/update local FBO wrapping the shared color texture.
        # The surface's FBO lives in the offscreen context and is not
        # accessible here (main window context). But the color texture
        # is shared between contexts, so we wrap it in a local FBO.
        if self._local_blit_fbo == 0:
            self._local_blit_fbo = int(glGenFramebuffers(1))

        if self._local_blit_tex != tex_id:
            glBindFramebuffer(GL_FRAMEBUFFER, self._local_blit_fbo)
            glFramebufferTexture2D(
                GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                GL_TEXTURE_2D, tex_id, 0,
            )
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            self._local_blit_tex = tex_id

        # Координаты виджета в GL (Y=0 снизу, Y-flip от экранных координат)
        vp_h = renderer._viewport_h
        dst_x = int(self.x)
        dst_y = int(vp_h - self.y - self.height)
        dst_w = int(self.width)
        dst_h = int(self.height)

        # Blit не использует scissor корректно на некоторых драйверах —
        # отключаем на время blit, восстанавливаем после
        glDisable(GL_SCISSOR_TEST)

        glBindFramebuffer(GL_READ_FRAMEBUFFER, self._local_blit_fbo)
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0)
        glBlitFramebuffer(
            0, 0, fbo_w, fbo_h,
            dst_x, dst_y, dst_x + dst_w, dst_y + dst_h,
            GL_COLOR_BUFFER_BIT, GL_LINEAR,
        )
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

        # Восстанавливаем scissor если был активен
        if renderer._clip_stack:
            px, py, pw, ph = renderer._clip_stack[-1]
            renderer._graphics.enable_scissor(px, py, pw, ph)

    # ------------------------------------------------------------------
    # Mouse events → input manager
    # ------------------------------------------------------------------

    def on_mouse_down(self, event: MouseEvent) -> bool:
        if self._input_manager_ptr:
            self._dispatch_mouse_button(event.button, 1, event.mods)
        return True

    def on_mouse_up(self, event: MouseEvent) -> None:
        if self._input_manager_ptr:
            self._dispatch_mouse_button(event.button, 0, event.mods)

    def on_mouse_move(self, event: MouseEvent) -> None:
        if self._input_manager_ptr:
            try:
                from termin._native.render import _input_manager_on_mouse_move
                _input_manager_on_mouse_move(
                    self._input_manager_ptr,
                    float(event.x - self.x), float(event.y - self.y),
                )
            except Exception:
                pass

    def on_mouse_wheel(self, event: MouseWheelEvent) -> bool:
        if self._input_manager_ptr:
            try:
                from termin._native.render import _input_manager_on_scroll
                _input_manager_on_scroll(
                    self._input_manager_ptr,
                    float(event.dx), float(event.dy), 0,
                )
            except Exception:
                pass
        return True

    def _dispatch_mouse_button(self, button, action: int, mods: int) -> None:
        from tcbase import MouseButton
        btn_map = {
            MouseButton.LEFT: 0,
            MouseButton.RIGHT: 1,
            MouseButton.MIDDLE: 2,
        }
        btn_id = btn_map.get(button, 0)
        try:
            from termin._native.render import _input_manager_on_mouse_button
            _input_manager_on_mouse_button(self._input_manager_ptr, btn_id, action, mods)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Key events → input manager
    # ------------------------------------------------------------------

    def on_key_down(self, event: KeyEvent) -> bool:
        if self._input_manager_ptr:
            self._dispatch_key(event, 1)
        return True

    def on_key_up(self, event: KeyEvent) -> bool:
        if self._input_manager_ptr:
            self._dispatch_key(event, 0)
        return True

    def _dispatch_key(self, event: KeyEvent, action: int) -> None:
        try:
            from termin._native.render import _input_manager_on_key
            _input_manager_on_key(
                self._input_manager_ptr,
                event.key.value, 0, action, event.mods,
            )
        except Exception:
            pass
