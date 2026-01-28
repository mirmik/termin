"""
DisplayInputManager — input handling for Display.

SimpleDisplayInputManager — basic handler for simple applications (examples).
Routes mouse/keyboard events to scene via InputComponents.

Each Python class has its own vtable registered once.
"""

from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from termin._native.render import (
    _input_manager_create_vtable,
    _input_manager_new,
    _input_manager_free,
    TC_INPUT_PRESS,
    TC_INPUT_RELEASE,
    TC_MOUSE_BUTTON_LEFT,
)
from termin.visualization.core.input_events import (
    MouseButtonEvent,
    MouseMoveEvent,
    ScrollEvent,
    KeyEvent,
    Action,
    MouseButton,
)

if TYPE_CHECKING:
    from termin.visualization.core.display import Display
    from termin.visualization.core.viewport import Viewport


# Class-level vtable pointer (created once per class)
_simple_vtable_ptr: int = 0


def _get_simple_vtable() -> int:
    """Get or create vtable for SimpleDisplayInputManager."""
    global _simple_vtable_ptr
    if _simple_vtable_ptr == 0:
        def on_mouse_button(manager, button, action, mods):
            manager._on_mouse_button(button, action, mods)

        def on_mouse_move(manager, x, y):
            manager._on_mouse_move(x, y)

        def on_scroll(manager, x, y, mods):
            manager._on_scroll(x, y, mods)

        def on_key(manager, key, scancode, action, mods):
            manager._on_key(key, scancode, action, mods)

        def on_char(manager, codepoint):
            pass  # Not used in simple manager

        _simple_vtable_ptr = _input_manager_create_vtable(
            on_mouse_button, on_mouse_move, on_scroll, on_key, on_char
        )
    return _simple_vtable_ptr


class SimpleDisplayInputManager:
    """
    Simple input handler for Display.

    Routes mouse and keyboard events to scene:
    - Mouse button -> on_mouse_button in InputComponents
    - Mouse move -> on_mouse_move in InputComponents
    - Scroll -> on_scroll in InputComponents
    - Key -> on_key in InputComponents

    Also handles:
    - Canvas UI events
    - Object click (raycast + on_click)
    - ESC to close window
    """

    def __init__(
        self,
        display: "Display",
        on_request_update: Callable[[], None] | None = None,
    ):
        """
        Create SimpleDisplayInputManager.

        Args:
            display: Display to route events to viewports.
            on_request_update: Callback to request redraw.
        """
        self._tc_input_manager_ptr: int = 0

        self._display = display
        self._on_request_update = on_request_update

        self._active_viewport: "Viewport | None" = None
        self._last_cursor: tuple[float, float] | None = None

        # Create tc_input_manager with class vtable
        vtable = _get_simple_vtable()
        self._tc_input_manager_ptr = _input_manager_new(vtable, self)

    def __del__(self):
        if self._tc_input_manager_ptr:
            _input_manager_free(self._tc_input_manager_ptr)
            self._tc_input_manager_ptr = 0

    @property
    def tc_input_manager_ptr(self) -> int:
        """Raw pointer to tc_input_manager (for C interop)."""
        return self._tc_input_manager_ptr

    @property
    def display(self) -> "Display":
        """Display that this input manager is attached to."""
        return self._display

    def _request_update(self) -> None:
        """Request redraw."""
        if self._on_request_update is not None:
            self._on_request_update()

    def _viewport_under_cursor(self, x: float, y: float) -> "Viewport | None":
        """Find viewport under cursor."""
        return self._display.viewport_at_pixels(x, y)

    def _viewport_rect_to_pixels(self, viewport: "Viewport") -> tuple[int, int, int, int]:
        """Convert viewport rect to pixels."""
        return self._display.viewport_rect_to_pixels(viewport)

    # ----------------------------------------------------------------
    # Event handlers (called via C callbacks)
    # ----------------------------------------------------------------

    def _on_mouse_button(self, button: int, action: int, mods: int) -> None:
        """Handle mouse button event."""
        # Get cursor position from display surface
        x, y = self._get_cursor_pos()
        viewport = self._viewport_under_cursor(x, y)

        # Track active viewport for drag operations
        if action == TC_INPUT_PRESS:
            self._active_viewport = viewport
        if action == TC_INPUT_RELEASE:
            self._last_cursor = None
            if viewport is None:
                viewport = self._active_viewport
            self._active_viewport = None

        # Convert C constants to Python enums
        py_button = MouseButton(button)
        py_action = Action(action)

        # Dispatch to scene
        if viewport is not None:
            event = MouseButtonEvent(
                viewport=viewport, x=x, y=y,
                button=py_button, action=py_action, mods=mods
            )
            viewport.scene.dispatch_input("on_mouse_button", event)

        # Object click handling (raycast)
        if viewport is not None and action == TC_INPUT_PRESS and button == TC_MOUSE_BUTTON_LEFT:
            cam = viewport.camera
            if cam is not None:
                rect = self._viewport_rect_to_pixels(viewport)
                ray = cam.screen_point_to_ray(x, y, viewport_rect=rect)
                hit = viewport.scene.raycast(ray)
                if hit is not None:
                    entity = hit.entity
                    for comp in entity.components:
                        on_click = getattr(comp, "on_click", None)
                        if on_click is not None:
                            on_click(hit, py_button)

        self._request_update()

    def _on_mouse_move(self, x: float, y: float) -> None:
        """Handle mouse move event."""
        if self._last_cursor is None:
            dx = dy = 0.0
        else:
            dx = x - self._last_cursor[0]
            dy = y - self._last_cursor[1]

        self._last_cursor = (x, y)
        viewport = self._active_viewport or self._viewport_under_cursor(x, y)

        # Dispatch to scene
        if viewport is not None:
            event = MouseMoveEvent(viewport=viewport, x=x, y=y, dx=dx, dy=dy)
            viewport.scene.dispatch_input("on_mouse_move", event)

        self._request_update()

    def _on_scroll(self, xoffset: float, yoffset: float, mods: int) -> None:
        """Handle scroll event."""
        x, y = self._get_cursor_pos()
        viewport = self._viewport_under_cursor(x, y) or self._active_viewport

        if viewport is not None:
            event = ScrollEvent(
                viewport=viewport, x=x, y=y,
                xoffset=xoffset, yoffset=yoffset, mods=mods
            )
            viewport.scene.dispatch_input("on_scroll", event)

        self._request_update()

    def _on_key(self, key: int, scancode: int, action: int, mods: int) -> None:
        """Handle key event."""
        from termin.visualization.platform.backends.base import Key

        # ESC closes window
        if key == Key.ESCAPE.value and action == TC_INPUT_PRESS:
            self._display.surface.set_should_close(True)

        py_action = Action(action)
        py_key = Key(key)

        viewport = self._active_viewport or (
            self._display.viewports[0] if self._display.viewports else None
        )

        if viewport is not None:
            event = KeyEvent(
                viewport=viewport,
                key=py_key, scancode=scancode, action=py_action, mods=mods
            )
            viewport.scene.dispatch_input("on_key", event)

        self._request_update()

    def _get_cursor_pos(self) -> tuple[float, float]:
        """Get cursor position from display surface."""
        return self._display.surface.get_cursor_pos()
