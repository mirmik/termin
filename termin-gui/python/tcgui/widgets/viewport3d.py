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
        if self._surface is None or self._surface.color_tex is None:
            # Render target not ready — placeholder rectangle
            renderer.draw_rect(self.x, self.y, self.width, self.height,
                               (0.05, 0.05, 0.05, 1.0))
            return

        self._composite_texture(renderer)

    def _composite_texture(self, renderer: 'UIRenderer') -> None:
        """Composite the 3D engine's offscreen tgfx2 texture into the
        UI pass via ``UIRenderer.draw_texture``.

        The surface's color texture and the renderer's Tgfx2Context
        live on the same IRenderDevice by construction (the host binds
        a process-global context in ``run_editor_tcgui``), so the
        handle is directly consumable — no GL-id wrap needed. Works on
        both OpenGL and Vulkan.

        ``flip_v=True`` because tgfx2 color attachments follow the GL
        origin convention (texel (0, 0) at the bottom-left), while the
        UI ortho projection samples top-left.
        """
        handle = self._surface.color_tex
        tex_w, tex_h = self._surface.framebuffer_size()
        if handle is None or tex_w == 0 or tex_h == 0:
            return

        renderer.draw_texture(
            self.x, self.y, self.width, self.height,
            handle=handle,
            tex_w=tex_w,
            tex_h=tex_h,
            flip_v=True,
        )

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
