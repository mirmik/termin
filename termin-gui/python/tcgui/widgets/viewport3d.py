"""Viewport3D — виджет для отображения 3D-сцены через FBO.

Принимает FBOSurface от FBOWindowBackend. На каждом кадре отображает
содержимое FBO через glBlitFramebuffer в область виджета.
Перенаправляет события мыши и клавиатуры в input manager 3D-движка.

Usage::

    surface = FBOSurface(width=800, height=600)
    display = Display(surface=surface, name="Editor")
    viewport = Viewport3D()
    viewport.set_surface(surface, display)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from tcgui.widgets.widget import Widget
from tcgui.widgets.events import DragEvent, MouseEvent, MouseWheelEvent, KeyEvent

if TYPE_CHECKING:
    from termin.display import FBOSurface
    from tcgui.widgets.renderer import UIRenderer


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
        self._display = None
        self._pointer_x = 0.0
        self._pointer_y = 0.0

        # Коллбек вызывается при изменении размера (до того как FBO пересоздан)
        self.on_before_resize: Callable[[int, int], None] | None = None
        self.on_external_drag: Callable[[DragEvent], bool] | None = None
        self.on_external_drop: Callable[[DragEvent], bool] | None = None

    # ------------------------------------------------------------------
    # Подключение
    # ------------------------------------------------------------------

    def set_surface(self, surface: FBOSurface, display=None) -> None:
        """Подключить FBOSurface и опционально Display для получения input manager."""
        self._surface = surface
        if display is not None:
            self._connect_input(display)
        self._sync_surface_size()

    def _sync_surface_size(self) -> None:
        """Resize a newly attached surface to the widget's current layout size.

        The tcgui editor can lay out and first-present the widget before
        FBOSurface exists. In that case later layout passes see unchanged
        widget dimensions and do not call resize(), leaving the surface at
        its constructor fallback size until the user manually resizes a panel.
        """
        if self._surface is None:
            return
        new_w = int(self.width)
        new_h = int(self.height)
        if new_w <= 0 or new_h <= 0:
            return
        old_w, old_h = self._surface.framebuffer_size()
        if (new_w, new_h) == (old_w, old_h):
            return
        if self.on_before_resize is not None:
            self.on_before_resize(new_w, new_h)
        self._surface.resize(new_w, new_h)

    def _connect_input(self, display) -> None:
        """Use the stable display-owned input endpoint."""
        self._display = display

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

        Sampling is `v=0 = visual top` on both backends — OpenGL
        achieves parity via a Y-flip on upload and a `texture()` macro
        wrapper in `OpenGLRenderDevice` (see coord_system.md §4). No
        backend branch needed here.
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
        )

    # ------------------------------------------------------------------
    # Mouse events → input manager
    # ------------------------------------------------------------------

    def on_mouse_down(self, event: MouseEvent) -> bool:
        if self._display is not None:
            self._sync_mouse_position(event)
            self._dispatch_mouse_button(event.button, 1, event.mods)
        return True

    def on_mouse_up(self, event: MouseEvent) -> None:
        if self._display is not None:
            self._sync_mouse_position(event)
            self._dispatch_mouse_button(event.button, 0, event.mods)

    def on_mouse_move(self, event: MouseEvent) -> None:
        self._sync_mouse_position(event)

    def _sync_mouse_position(self, event: MouseEvent | MouseWheelEvent) -> None:
        from tcbase import log
        if self._display is not None and self._surface is not None:
            try:
                pixel_width, pixel_height = self._surface.framebuffer_size()
                self._pointer_x = float(event.x - self.x) * pixel_width / max(self.width, 1.0)
                self._pointer_y = float(event.y - self.y) * pixel_height / max(self.height, 1.0)
                self._display.dispatch_pointer_move(self._pointer_x, self._pointer_y)
            except Exception as e:
                log.error(f"Viewport3D._sync_mouse_position: {e}")

    def on_mouse_wheel(self, event: MouseWheelEvent) -> bool:
        from tcbase import log
        if self._display is not None:
            self._sync_mouse_position(event)
            try:
                self._display.dispatch_wheel(
                    self._pointer_x,
                    self._pointer_y,
                    float(event.dx),
                    float(event.dy),
                    event.mods,
                )
            except Exception as e:
                log.error(f"Viewport3D.on_mouse_wheel: {e}")
        return True

    def on_drag_move(self, event: DragEvent) -> bool:
        if self.on_external_drag is None:
            return False
        return bool(self.on_external_drag(event))

    def on_drag_drop(self, event: DragEvent) -> bool:
        if self.on_external_drop is None:
            return False
        return bool(self.on_external_drop(event))

    def _dispatch_mouse_button(self, button, action: int, mods: int) -> None:
        from tcbase import MouseButton, log
        btn_map = {
            MouseButton.LEFT: 0,
            MouseButton.RIGHT: 1,
            MouseButton.MIDDLE: 2,
        }
        btn_id = btn_map.get(button, 0)
        try:
            self._display.dispatch_pointer_button(
                self._pointer_x, self._pointer_y, btn_id, action, mods, 1
            )
        except Exception as e:
            log.error(f"Viewport3D._dispatch_mouse_button: {e}")

    # ------------------------------------------------------------------
    # Key events → input manager
    # ------------------------------------------------------------------

    def on_key_down(self, event: KeyEvent) -> bool:
        if self._display is not None:
            self._dispatch_key(event, 1)
        return True

    def on_key_up(self, event: KeyEvent) -> bool:
        if self._display is not None:
            self._dispatch_key(event, 0)
        return True

    def _dispatch_key(self, event: KeyEvent, action: int) -> None:
        from tcbase import log
        try:
            self._display.dispatch_key(event.key.value, 0, action, event.mods)
        except Exception as e:
            log.error(f"Viewport3D._dispatch_key: {e}")
