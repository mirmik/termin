"""
EditorDisplayInputManager — input handling for editor.

Extends SimpleDisplayInputManager functionality:
- Support for editor mode vs game mode
- Picking via ID buffer
- External callbacks for editor events

Each Python class has its own vtable registered once.
"""

from __future__ import annotations

import time
from typing import Callable, TYPE_CHECKING

from termin._native.render import (
    _input_manager_create_vtable,
    _input_manager_new,
    _input_manager_free,
    TC_INPUT_PRESS,
    TC_INPUT_RELEASE,
)
from termin.visualization.core.camera import CameraController
from termin.visualization.core.entity import Entity
from termin.visualization.core.picking import rgb_to_id
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
    from termin.visualization.platform.backends.base import (
        FramebufferHandle,
        GraphicsBackend,
    )


# Class-level vtable pointer (created once per class)
_editor_vtable_ptr: int = 0


def _get_editor_vtable() -> int:
    """Get or create vtable for EditorDisplayInputManager."""
    global _editor_vtable_ptr
    if _editor_vtable_ptr == 0:
        def on_mouse_button(manager, button, action, mods):
            manager._on_mouse_button(button, action, mods)

        def on_mouse_move(manager, x, y):
            manager._on_mouse_move(x, y)

        def on_scroll(manager, x, y, mods):
            manager._on_scroll(x, y, mods)

        def on_key(manager, key, scancode, action, mods):
            manager._on_key(key, scancode, action, mods)

        def on_char(manager, codepoint):
            pass  # Not used in editor manager

        _editor_vtable_ptr = _input_manager_create_vtable(
            on_mouse_button, on_mouse_move, on_scroll, on_key, on_char
        )
    return _editor_vtable_ptr


class EditorDisplayInputManager:
    """
    Input handler for editor.

    Supports two modes:
    - "editor": editor mode with picking, gizmo, external callbacks
    - "game": game mode, routes events to scene

    For picking requires access to FBO pool via get_fbo_pool callback.
    """

    def __init__(
        self,
        display: "Display",
        graphics: "GraphicsBackend",
        get_fbo_pool: Callable[[], dict] | None = None,
        on_request_update: Callable[[], None] | None = None,
        on_mouse_button_event: Callable[[MouseButton, Action, float, float, "Viewport | None"], None] | None = None,
        on_mouse_move_event: Callable[[float, float, "Viewport | None"], None] | None = None,
    ):
        """
        Create EditorDisplayInputManager.

        Args:
            display: Display to route events to viewports.
            graphics: GraphicsBackend for reading pixels from FBO.
            get_fbo_pool: Callback to get FBO pool (for picking).
            on_request_update: Callback to request redraw.
            on_mouse_button_event: Callback for external click handling.
            on_mouse_move_event: Callback for external mouse move handling.
        """
        self._tc_input_manager_ptr: int = 0

        self._display = display
        self._graphics = graphics
        self._get_fbo_pool = get_fbo_pool
        self._on_request_update = on_request_update
        self._on_mouse_button_event = on_mouse_button_event
        self._on_mouse_move_event = on_mouse_move_event

        self._active_viewport: "Viewport | None" = None
        self._last_cursor: tuple[float, float] | None = None
        self._world_mode = "editor"  # "editor" or "game"

        # Double-click tracking
        self._last_click_time: float = 0.0
        self._double_click_threshold: float = 0.3

        # Current modifier keys state (updated on key events)
        self._current_mods: int = 0

        # Create tc_input_manager with class vtable
        vtable = _get_editor_vtable()
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

    @property
    def world_mode(self) -> str:
        """Current mode: 'editor' or 'game'."""
        return self._world_mode

    def set_world_mode(self, mode: str) -> None:
        """Set operating mode."""
        self._world_mode = mode

    def _dispatch_to_camera(self, viewport: "Viewport", event_name: str, event) -> None:
        """Dispatch event to InputComponents on viewport's camera.

        Checks is_input_handler via tc_component API, not via isinstance,
        since C++ components (e.g. OrbitCameraController) don't inherit Python InputComponent.
        """
        camera = viewport.camera
        if camera is None:
            print(f"[_dispatch_to_camera] {event_name}: camera is None")
            return
        if camera.entity is None:
            print(f"[_dispatch_to_camera] {event_name}: camera.entity is None")
            return
        for comp in camera.entity.components:
            # Check via tc_component_is_input_handler (C API)
            is_handler = comp.is_input_handler
            if is_handler:
                handler = getattr(comp, event_name, None)
                if handler:
                    print(f"[_dispatch_to_camera] calling {type(comp).__name__}.{event_name}")
                    handler(event)
                else:
                    print(f"[_dispatch_to_camera] {type(comp).__name__} has no {event_name}")

    def _dispatch_to_editor_components(self, viewport: "Viewport", event_name: str, event) -> None:
        """Dispatch event to InputComponents in scene with active_in_editor=True."""
        scene = viewport.scene
        if scene is None:
            return
        # Use fast-path C-level dispatch with active_in_editor filter
        if event_name == "on_mouse_button":
            scene.dispatch_mouse_button_editor(event)
        elif event_name == "on_mouse_move":
            scene.dispatch_mouse_move_editor(event)
        elif event_name == "on_scroll":
            scene.dispatch_scroll_editor(event)
        elif event_name == "on_key":
            scene.dispatch_key_editor(event)

    def _dispatch_to_internal_entities(self, viewport: "Viewport", event_name: str, event) -> None:
        """Dispatch event to InputComponents in viewport.internal_entities."""
        internal_root = viewport.internal_entities
        if internal_root is None:
            return
        self._dispatch_to_entity_hierarchy(internal_root, event_name, event)

    def _dispatch_to_entity_hierarchy(self, entity: "Entity", event_name: str, event) -> None:
        """Recursively dispatch event to InputComponents of entity and its children.

        Checks is_input_handler via tc_component API.
        """
        for comp in entity.components:
            if comp.is_input_handler and comp.enabled:
                handler = getattr(comp, event_name, None)
                if handler:
                    handler(event)

        for child_tf in entity.transform.children:
            if child_tf.entity is not None:
                self._dispatch_to_entity_hierarchy(child_tf.entity, event_name, event)

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

    def _get_cursor_pos(self) -> tuple[float, float]:
        """Get cursor position from display surface."""
        return self._display.surface.get_cursor_pos()

    # ----------------------------------------------------------------
    # Picking support
    # ----------------------------------------------------------------

    def pick_color_at(
        self,
        x: float,
        y: float,
        viewport: "Viewport | None" = None,
        buffer_name: str = "color",
    ) -> tuple[float, float, float, float] | None:
        """
        Read pixel color from FBO.

        Args:
            x, y: coordinates in window pixels (origin top-left).
            viewport: viewport to read from (auto-detected if None).
            buffer_name: resource name in fbo_pool.

        Returns:
            (r, g, b, a) in [0..1] or None.
        """
        if self._get_fbo_pool is None:
            return None

        fbo_pool = self._get_fbo_pool()
        if fbo_pool is None:
            return None

        if viewport is None:
            viewport = self._viewport_under_cursor(x, y)
            if viewport is None:
                return None

        surface = self._display.surface
        win_w, win_h = surface.window_size()
        fb_w, fb_h = surface.get_size()

        if win_w <= 0 or win_h <= 0 or fb_w <= 0 or fb_h <= 0:
            return None

        px, py, pw, ph = self._viewport_rect_to_pixels(viewport)

        # Convert mouse coordinates from logical to physical
        sx = fb_w / float(win_w)
        sy = fb_h / float(win_h)
        x_phys = x * sx
        y_phys = y * sy

        # Local coordinates within viewport
        vx = x_phys - px
        vy = y_phys - py

        if vx < 0 or vy < 0 or vx >= pw or vy >= ph:
            return None

        # Convert to FBO coordinates (origin bottom-left)
        read_x = int(vx)
        read_y = int(ph - vy - 1)

        fb = fbo_pool.get_fbo(buffer_name)
        if fb is None:
            return None

        r, g, b, a = self._graphics.read_pixel(fb, read_x, read_y)
        # Return framebuffer back to window
        window_fb = surface.get_framebuffer()
        self._graphics.bind_framebuffer(window_fb)
        return (r, g, b, a)

    def pick_entity_at(
        self,
        x: float,
        y: float,
        viewport: "Viewport | None" = None,
    ) -> Entity | None:
        """
        Read entity under pixel from id-map.

        Args:
            x, y: coordinates in window pixels.
            viewport: viewport to read from.

        Returns:
            Entity or None.
        """
        if viewport is None:
            viewport = self._viewport_under_cursor(x, y)
            if viewport is None:
                return None
        color = self.pick_color_at(x, y, viewport, buffer_name="id")
        if color is None:
            return None
        r, g, b, a = color
        pid = rgb_to_id(r, g, b)
        if pid == 0:
            return None
        return viewport.scene.get_entity_by_pick_id(pid)

    def pick_depth_at(
        self,
        x: float,
        y: float,
        viewport: "Viewport | None" = None,
        buffer_name: str = "id",
    ) -> float | None:
        """
        Read depth under pixel from specified buffer.

        Args:
            x, y: coordinates in window pixels.
            viewport: viewport to read from.
            buffer_name: buffer name in FBO pool (default 'id').

        Returns:
            Depth in range [0, 1] or None.
        """
        if self._get_fbo_pool is None:
            return None

        fbo_pool = self._get_fbo_pool()
        if fbo_pool is None:
            return None

        if viewport is None:
            viewport = self._viewport_under_cursor(x, y)
            if viewport is None:
                return None

        surface = self._display.surface
        win_w, win_h = surface.window_size()
        fb_w, fb_h = surface.get_size()

        if win_w <= 0 or win_h <= 0 or fb_w <= 0 or fb_h <= 0:
            return None

        px, py, pw, ph = self._viewport_rect_to_pixels(viewport)

        # Convert mouse coordinates from logical to physical
        sx = fb_w / float(win_w)
        sy = fb_h / float(win_h)
        x_phys = x * sx
        y_phys = y * sy

        # Local coordinates within viewport
        vx = x_phys - px
        vy = y_phys - py

        if vx < 0 or vy < 0 or vx >= pw or vy >= ph:
            return None

        # Convert to FBO coordinates (origin bottom-left)
        read_x = int(vx)
        read_y = int(ph - vy - 1)

        fb = fbo_pool.get_fbo(buffer_name)
        if fb is None:
            return None

        depth = self._graphics.read_depth_pixel(fb, read_x, read_y)
        # Return framebuffer back to window
        window_fb = surface.get_framebuffer()
        self._graphics.bind_framebuffer(window_fb)
        return depth

    # ----------------------------------------------------------------
    # Event handlers (called via C callbacks)
    # ----------------------------------------------------------------

    def _on_mouse_button(self, button: int, action: int, mods: int) -> None:
        """Handle mouse button event."""
        print(f"[EditorDisplayInputManager] _on_mouse_button: button={button}, action={action}, mods={mods}")
        if self._world_mode == "game":
            self._handle_mouse_button_game_mode(button, action, mods)
        else:
            self._handle_mouse_button_editor_mode(button, action, mods)

    def _handle_mouse_button_game_mode(self, button: int, action: int, mods: int) -> None:
        """Handle click in game mode."""
        x, y = self._get_cursor_pos()
        viewport = self._viewport_under_cursor(x, y)

        py_button = MouseButton(button)
        py_action = Action(action)

        # Track active viewport
        if action == TC_INPUT_PRESS:
            self._active_viewport = viewport
        if action == TC_INPUT_RELEASE:
            self._last_cursor = None
            if viewport is None:
                viewport = self._active_viewport
            self._active_viewport = None

        # Dispatch to camera
        if viewport is not None:
            event = MouseButtonEvent(
                viewport=viewport, x=x, y=y,
                button=py_button, action=py_action, mods=mods
            )
            self._dispatch_to_camera(viewport, "on_mouse_button", event)

        # Object click handling (raycast)
        if viewport is not None and action == TC_INPUT_PRESS and button == 0:  # LEFT
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

        # Editor callbacks for picking/gizmo (allow editing in game mode)
        if self._on_mouse_button_event is not None:
            self._on_mouse_button_event(py_button, py_action, x, y, viewport)

        self._request_update()

    def _handle_mouse_button_editor_mode(self, button: int, action: int, mods: int) -> None:
        """Handle click in editor mode."""
        x, y = self._get_cursor_pos()
        viewport = self._viewport_under_cursor(x, y)

        py_button = MouseButton(button)
        py_action = Action(action)

        # Double-click detection
        is_double_click = False
        if action == TC_INPUT_PRESS and button == 0:  # LEFT
            current_time = time.time()
            if current_time - self._last_click_time < self._double_click_threshold:
                is_double_click = True
            self._last_click_time = current_time

        # Track active viewport
        if action == TC_INPUT_PRESS:
            self._active_viewport = viewport
        if action == TC_INPUT_RELEASE:
            self._last_cursor = None
            if viewport is None:
                viewport = self._active_viewport
            self._active_viewport = None

        # Dispatch to camera and editor components
        if viewport is not None:
            event = MouseButtonEvent(
                viewport=viewport, x=x, y=y,
                button=py_button, action=py_action, mods=mods
            )
            self._dispatch_to_internal_entities(viewport, "on_mouse_button", event)
            self._dispatch_to_editor_components(viewport, "on_mouse_button", event)
            self._dispatch_to_camera(viewport, "on_mouse_button", event)

        # Double-click: center camera on clicked entity
        if is_double_click and viewport is not None:
            self._handle_double_click(x, y, viewport)

        # External callback for editor (picking, gizmo, etc.)
        if self._on_mouse_button_event is not None:
            self._on_mouse_button_event(py_button, py_action, x, y, viewport)

        self._request_update()

    def _handle_double_click(self, x: float, y: float, viewport: "Viewport") -> None:
        """Handle double-click — center camera on object."""
        entity = self.pick_entity_at(x, y, viewport)
        if entity is None:
            return

        # Get entity position
        target_position = entity.transform.global_pose().lin

        # Find camera controller
        camera = viewport.camera
        if camera is None or camera.entity is None:
            return

        controller = camera.entity.get_component(CameraController)
        if controller is not None:
            controller.center_on(target_position)

    def _on_mouse_move(self, x: float, y: float) -> None:
        """Handle mouse move event."""
        if self._last_cursor is None:
            dx = dy = 0.0
        else:
            dx = x - self._last_cursor[0]
            dy = y - self._last_cursor[1]

        self._last_cursor = (x, y)
        viewport = self._active_viewport or self._viewport_under_cursor(x, y)

        if viewport is None:
            print(f"[EditorDisplayInputManager] _on_mouse_move: NO VIEWPORT at ({x:.0f}, {y:.0f})")
            return

        # Dispatch to editor components and camera
        event = MouseMoveEvent(viewport=viewport, x=x, y=y, dx=dx, dy=dy)
        self._dispatch_to_internal_entities(viewport, "on_mouse_move", event)
        self._dispatch_to_editor_components(viewport, "on_mouse_move", event)
        self._dispatch_to_camera(viewport, "on_mouse_move", event)

        # External callback
        if self._on_mouse_move_event is not None:
            self._on_mouse_move_event(x, y, viewport)

        self._request_update()

    def _on_scroll(self, xoffset: float, yoffset: float, mods: int) -> None:
        """Handle scroll event."""
        x, y = self._get_cursor_pos()
        viewport = self._viewport_under_cursor(x, y) or self._active_viewport

        # Use mods from parameter if provided, otherwise fall back to tracked mods
        actual_mods = mods if mods != 0 else self._current_mods

        if viewport is not None:
            event = ScrollEvent(
                viewport=viewport, x=x, y=y,
                xoffset=xoffset, yoffset=yoffset,
                mods=actual_mods
            )
            self._dispatch_to_internal_entities(viewport, "on_scroll", event)
            self._dispatch_to_editor_components(viewport, "on_scroll", event)
            self._dispatch_to_camera(viewport, "on_scroll", event)

        self._request_update()

    def _on_key(self, key: int, scancode: int, action: int, mods: int) -> None:
        """Handle key event."""
        from termin.visualization.platform.backends.base import Key

        # Update current mods state for use in scroll events
        self._current_mods = mods

        # ESC in game mode closes window
        if self._world_mode == "game" and key == Key.ESCAPE.value and action == TC_INPUT_PRESS:
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
            self._dispatch_to_internal_entities(viewport, "on_key", event)
            self._dispatch_to_editor_components(viewport, "on_key", event)
            self._dispatch_to_camera(viewport, "on_key", event)

        self._request_update()
