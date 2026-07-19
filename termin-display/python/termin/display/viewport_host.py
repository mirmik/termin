"""Adapter joining a render surface with a display-owned input endpoint."""

from __future__ import annotations


class DisplayViewportHost:
    """Viewport3D host with rendering delegated to surface and input to display."""

    def __init__(self, surface, display) -> None:
        self._surface = surface
        self._display = display
        self._pointer_x = 0.0
        self._pointer_y = 0.0

    def is_valid(self) -> bool:
        return self._surface.is_valid() and self._display.is_valid()

    def get_tgfx_color_tex_id(self) -> int:
        return self._surface.get_tgfx_color_tex_id()

    def framebuffer_size(self) -> tuple[int, int]:
        return self._surface.framebuffer_size()

    def resize(self, width: int, height: int) -> bool:
        return self._surface.resize(width, height)

    def dispatch_pointer_move(self, x: float, y: float) -> bool:
        self._pointer_x = x
        self._pointer_y = y
        return self._display.dispatch_pointer_move(x, y)

    def dispatch_pointer_button(
        self, button: int, action: int, modifiers: int, click_count: int
    ) -> bool:
        return self._display.dispatch_pointer_button(
            self._pointer_x, self._pointer_y, button, action, modifiers, click_count
        )

    def dispatch_scroll(self, wheel_x: float, wheel_y: float, modifiers: int) -> bool:
        return self._display.dispatch_wheel(
            self._pointer_x, self._pointer_y, wheel_x, wheel_y, modifiers
        )

    def dispatch_key(self, key: int, scancode: int, action: int, modifiers: int) -> bool:
        return self._display.dispatch_key(key, scancode, action, modifiers)

    def dispatch_text(self, codepoint: int) -> bool:
        return self._display.dispatch_text(codepoint)


__all__ = ["DisplayViewportHost"]
