"""SDL2 backend for embedding into Qt widgets.

Creates a standalone SDL+OpenGL window and embeds it into Qt layout
using QWindow.fromWinId() + QWidget.createWindowContainer().
"""

from __future__ import annotations

import ctypes
import sys
from typing import Any, Callable, Optional, Tuple, TYPE_CHECKING

import sdl2
from sdl2 import video

from .base import Action, BackendWindow, Key, MouseButton, WindowBackend

from termin.graphics import OpenGLGraphicsBackend

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget


def _translate_qt_key(qt_key: int) -> Key:
    """Translate Qt key code to our Key enum."""
    from PyQt6.QtCore import Qt
    mapping = {
        # Special keys
        Qt.Key.Key_Escape: Key.ESCAPE,
        Qt.Key.Key_Space: Key.SPACE,
        Qt.Key.Key_Return: Key.ENTER,
        Qt.Key.Key_Enter: Key.ENTER,
        Qt.Key.Key_Tab: Key.TAB,
        Qt.Key.Key_Backspace: Key.BACKSPACE,
        Qt.Key.Key_Delete: Key.DELETE,
        Qt.Key.Key_Left: Key.LEFT,
        Qt.Key.Key_Right: Key.RIGHT,
        Qt.Key.Key_Up: Key.UP,
        Qt.Key.Key_Down: Key.DOWN,
        # Function keys
        Qt.Key.Key_F1: Key.F1,
        Qt.Key.Key_F2: Key.F2,
        Qt.Key.Key_F3: Key.F3,
        Qt.Key.Key_F4: Key.F4,
        Qt.Key.Key_F5: Key.F5,
        Qt.Key.Key_F6: Key.F6,
        Qt.Key.Key_F7: Key.F7,
        Qt.Key.Key_F8: Key.F8,
        Qt.Key.Key_F9: Key.F9,
        Qt.Key.Key_F10: Key.F10,
        Qt.Key.Key_F11: Key.F11,
        Qt.Key.Key_F12: Key.F12,
    }
    if qt_key in mapping:
        return mapping[qt_key]
    # For ASCII keys (A-Z, 0-9, etc.) - Qt uses ASCII values
    if 0 <= qt_key < 128:
        try:
            return Key(qt_key)
        except ValueError:
            pass
    return Key.UNKNOWN


def _translate_qt_mods(qt_mods) -> int:
    """Translate Qt modifiers to GLFW-compatible flags."""
    from PyQt6.QtCore import Qt
    result = 0
    if qt_mods & Qt.KeyboardModifier.ShiftModifier:
        result |= 0x0001  # MOD_SHIFT
    if qt_mods & Qt.KeyboardModifier.ControlModifier:
        result |= 0x0002  # MOD_CONTROL
    if qt_mods & Qt.KeyboardModifier.AltModifier:
        result |= 0x0004  # MOD_ALT
    return result


class QtKeyEventFilter:
    """Event filter that forwards Qt keyboard events to SDL callbacks."""

    def __init__(self, backend_window: "SDLEmbeddedWindowHandle"):
        from PyQt6.QtCore import QObject, QEvent

        self._backend_window = backend_window
        self._filter = _QtEventFilterImpl(self)

    def install(self, widget: "QWidget") -> None:
        """Install filter on widget."""
        widget.installEventFilter(self._filter._impl)

    def handle_key_event(self, event) -> bool:
        """Handle Qt key event, forward to SDL callback."""
        from PyQt6.QtCore import QEvent, Qt
        from termin._native import log

        is_press = event.type() == QEvent.Type.KeyPress
        is_release = event.type() == QEvent.Type.KeyRelease

        if not (is_press or is_release):
            return False

        qt_key = event.key()
        key = _translate_qt_key(qt_key)
        scancode = event.nativeScanCode()

        # Track modifier keys state
        if qt_key in (Qt.Key.Key_Shift, Qt.Key.Key_Meta):
            self._backend_window._shift_pressed = is_press
        elif qt_key in (Qt.Key.Key_Control,):
            self._backend_window._ctrl_pressed = is_press
        elif qt_key in (Qt.Key.Key_Alt,):
            self._backend_window._alt_pressed = is_press

        # Build mods from our tracked state
        mods = self._backend_window.get_tracked_mods()

        if is_press:
            action = Action.REPEAT if event.isAutoRepeat() else Action.PRESS
            log.info(f"[Qt->SDL] KEYDOWN: key={key}, mods={mods}")
        else:
            action = Action.RELEASE
            log.info(f"[Qt->SDL] KEYUP: key={key}, mods={mods}")

        if self._backend_window._key_callback is not None:
            self._backend_window._key_callback(
                self._backend_window, key, scancode, action, mods
            )
            return True

        return False


class _QtEventFilterImpl:
    """QObject-based event filter implementation."""

    def __init__(self, handler: QtKeyEventFilter):
        from PyQt6.QtCore import QObject

        class Filter(QObject):
            def __init__(self, h):
                super().__init__()
                self._handler = h

            def eventFilter(self, obj, event):
                from PyQt6.QtCore import QEvent
                if event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
                    if self._handler.handle_key_event(event):
                        return True
                return super().eventFilter(obj, event)

        self._impl = Filter(handler)

    def __getattr__(self, name):
        return getattr(self._impl, name)


_sdl_initialized = False


def _ensure_sdl() -> None:
    global _sdl_initialized
    if not _sdl_initialized:
        if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
            raise RuntimeError(f"Failed to initialize SDL: {sdl2.SDL_GetError()}")
        _sdl_initialized = True


def _translate_mouse_button(button: int) -> MouseButton:
    mapping = {
        sdl2.SDL_BUTTON_LEFT: MouseButton.LEFT,
        sdl2.SDL_BUTTON_RIGHT: MouseButton.RIGHT,
        sdl2.SDL_BUTTON_MIDDLE: MouseButton.MIDDLE,
    }
    return mapping.get(button, MouseButton.LEFT)


def _translate_key(scancode: int) -> Key:
    if scancode == sdl2.SDL_SCANCODE_ESCAPE:
        return Key.ESCAPE
    if scancode == sdl2.SDL_SCANCODE_SPACE:
        return Key.SPACE
    keycode = sdl2.SDL_GetKeyFromScancode(scancode)
    if 0 <= keycode < 128:
        try:
            return Key(keycode)
        except ValueError:
            pass
    return Key.UNKNOWN


def _translate_sdl_mods(sdl_mods: int) -> int:
    """Translate SDL modifier flags to GLFW-compatible flags."""
    # SDL: KMOD_LSHIFT=0x0001, KMOD_RSHIFT=0x0002
    # SDL: KMOD_LCTRL=0x0040, KMOD_RCTRL=0x0080
    # SDL: KMOD_LALT=0x0100, KMOD_RALT=0x0200
    # GLFW: SHIFT=0x0001, CTRL=0x0002, ALT=0x0004, SUPER=0x0008
    result = 0
    if sdl_mods & (sdl2.KMOD_LSHIFT | sdl2.KMOD_RSHIFT):
        result |= 0x0001  # MOD_SHIFT
    if sdl_mods & (sdl2.KMOD_LCTRL | sdl2.KMOD_RCTRL):
        result |= 0x0002  # MOD_CONTROL
    if sdl_mods & (sdl2.KMOD_LALT | sdl2.KMOD_RALT):
        result |= 0x0004  # MOD_ALT
    return result


def _get_qt_keyboard_mods() -> int:
    """Get keyboard modifiers from Qt (since SDL doesn't receive key events when embedded)."""
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        qt_mods = QApplication.keyboardModifiers()
        result = 0
        if qt_mods & Qt.KeyboardModifier.ShiftModifier:
            result |= 0x0001  # MOD_SHIFT
        if qt_mods & Qt.KeyboardModifier.ControlModifier:
            result |= 0x0002  # MOD_CONTROL
        if qt_mods & Qt.KeyboardModifier.AltModifier:
            result |= 0x0004  # MOD_ALT
        return result
    except Exception:
        return 0


def _get_native_window_handle(sdl_window) -> int:
    """Get native window handle from SDL window (HWND on Windows, Window on X11)."""
    wm_info = sdl2.SDL_SysWMinfo()
    sdl2.SDL_VERSION(wm_info.version)

    if not sdl2.SDL_GetWindowWMInfo(sdl_window, ctypes.byref(wm_info)):
        raise RuntimeError(f"Failed to get window info: {sdl2.SDL_GetError()}")

    if sys.platform == "win32":
        return wm_info.info.win.window
    elif sys.platform == "darwin":
        # macOS - NSWindow pointer
        return wm_info.info.cocoa.window
    else:
        # Linux/X11
        return wm_info.info.x11.window


class SDLEmbeddedWindowHandle(BackendWindow):
    """SDL2 window with OpenGL context, embeddable into Qt."""

    def __init__(
        self,
        width: int = 800,
        height: int = 600,
        title: str = "SDL Viewport",
        share_context: Optional[Any] = None,
        graphics: Optional[OpenGLGraphicsBackend] = None,
    ):
        _ensure_sdl()

        # OpenGL attributes
        video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MAJOR_VERSION, 3)
        video.SDL_GL_SetAttribute(video.SDL_GL_CONTEXT_MINOR_VERSION, 3)
        video.SDL_GL_SetAttribute(
            video.SDL_GL_CONTEXT_PROFILE_MASK,
            video.SDL_GL_CONTEXT_PROFILE_CORE,
        )
        video.SDL_GL_SetAttribute(video.SDL_GL_DOUBLEBUFFER, 1)
        video.SDL_GL_SetAttribute(video.SDL_GL_DEPTH_SIZE, 24)

        # Enable context sharing if a context is provided
        if share_context is not None:
            video.SDL_GL_SetAttribute(video.SDL_GL_SHARE_WITH_CURRENT_CONTEXT, 1)
            # Make the share context current before creating new context
            # (SDL requires this for context sharing)

        # Create SDL window with OpenGL support
        flags = (
            video.SDL_WINDOW_OPENGL
            | video.SDL_WINDOW_RESIZABLE
            | video.SDL_WINDOW_SHOWN
        )

        self._window = video.SDL_CreateWindow(
            title.encode("utf-8"),
            video.SDL_WINDOWPOS_UNDEFINED,
            video.SDL_WINDOWPOS_UNDEFINED,
            width,
            height,
            flags,
        )

        if not self._window:
            raise RuntimeError(f"Failed to create SDL window: {sdl2.SDL_GetError()}")

        self._gl_context = video.SDL_GL_CreateContext(self._window)
        if not self._gl_context:
            video.SDL_DestroyWindow(self._window)
            raise RuntimeError(f"Failed to create GL context: {sdl2.SDL_GetError()}")

        # Disable context sharing attribute for future windows that don't need it
        if share_context is not None:
            video.SDL_GL_SetAttribute(video.SDL_GL_SHARE_WITH_CURRENT_CONTEXT, 0)

        video.SDL_GL_MakeCurrent(self._window, self._gl_context)

        # Disable VSync - we control frame rate ourselves
        video.SDL_GL_SetSwapInterval(0)

        # Get native handle for Qt embedding
        self._native_handle = _get_native_window_handle(self._window)

        # Callbacks
        self._framebuffer_size_callback: Optional[Callable] = None
        self._cursor_pos_callback: Optional[Callable] = None
        self._scroll_callback: Optional[Callable] = None
        self._mouse_button_callback: Optional[Callable] = None
        self._key_callback: Optional[Callable] = None
        self._focus_callback: Optional[Callable] = None

        # Track modifier keys state (since Qt modifiers lag by one frame)
        self._shift_pressed = False
        self._ctrl_pressed = False
        self._alt_pressed = False

        self._user_pointer: Any = None
        self._should_close = False
        self._needs_render = True

        # Cache for window framebuffer handle
        self._window_fb_handle: Optional[Any] = None

        # Last known size for resize detection
        self._last_width = width
        self._last_height = height

        # Graphics backend for framebuffer creation
        self._graphics = graphics

    @property
    def native_handle(self) -> int:
        """Native window handle for Qt embedding."""
        return self._native_handle

    def show(self) -> None:
        """Show the SDL window."""
        if self._window is not None:
            video.SDL_ShowWindow(self._window)

    def close(self) -> None:
        if self._gl_context:
            video.SDL_GL_DeleteContext(self._gl_context)
            self._gl_context = None
        if self._window:
            video.SDL_DestroyWindow(self._window)
            self._window = None

    def should_close(self) -> bool:
        return self._should_close or self._window is None

    def make_current(self) -> None:
        if self._window is not None and self._gl_context is not None:
            video.SDL_GL_MakeCurrent(self._window, self._gl_context)

    def swap_buffers(self) -> None:
        if self._window is not None:
            # Check current context before swap
            current_ctx = video.SDL_GL_GetCurrentContext()
            if current_ctx != self._gl_context:
                print(f"WARNING: Wrong context before swap! Expected {self._gl_context}, got {current_ctx}")
            video.SDL_GL_SwapWindow(self._window)

    def framebuffer_size(self) -> Tuple[int, int]:
        if self._window is None:
            return (0, 0)
        w = ctypes.c_int()
        h = ctypes.c_int()
        video.SDL_GL_GetDrawableSize(self._window, ctypes.byref(w), ctypes.byref(h))
        return (w.value, h.value)

    def window_size(self) -> Tuple[int, int]:
        if self._window is None:
            return (0, 0)
        w = ctypes.c_int()
        h = ctypes.c_int()
        video.SDL_GetWindowSize(self._window, ctypes.byref(w), ctypes.byref(h))
        return (w.value, h.value)

    def get_cursor_pos(self) -> Tuple[float, float]:
        x = ctypes.c_int()
        y = ctypes.c_int()
        sdl2.SDL_GetMouseState(ctypes.byref(x), ctypes.byref(y))
        return (float(x.value), float(y.value))

    def set_should_close(self, flag: bool) -> None:
        self._should_close = flag

    def set_user_pointer(self, ptr: Any) -> None:
        self._user_pointer = ptr

    def set_framebuffer_size_callback(self, callback: Callable) -> None:
        self._framebuffer_size_callback = callback

    def set_cursor_pos_callback(self, callback: Callable) -> None:
        self._cursor_pos_callback = callback

    def set_scroll_callback(self, callback: Callable) -> None:
        self._scroll_callback = callback

    def set_mouse_button_callback(self, callback: Callable) -> None:
        self._mouse_button_callback = callback

    def set_key_callback(self, callback: Callable) -> None:
        self._key_callback = callback

    def set_focus_callback(self, callback: Callable) -> None:
        """Set callback to request focus (called on mouse click)."""
        self._focus_callback = callback

    def get_tracked_mods(self) -> int:
        """Get modifier flags from tracked key state."""
        mods = 0
        if self._shift_pressed:
            mods |= 0x0001  # MOD_SHIFT
        if self._ctrl_pressed:
            mods |= 0x0002  # MOD_CONTROL
        if self._alt_pressed:
            mods |= 0x0004  # MOD_ALT
        return mods

    def install_qt_key_filter(self, widget: "QWidget") -> None:
        """Install Qt event filter to forward keyboard events to this window."""
        self._qt_key_filter = QtKeyEventFilter(self)
        self._qt_key_filter.install(widget)

    def drives_render(self) -> bool:
        # Pull model - we control rendering explicitly
        return False

    def request_update(self) -> None:
        self._needs_render = True

    def needs_render(self) -> bool:
        return self._needs_render

    def clear_render_flag(self) -> None:
        self._needs_render = False

    def get_window_framebuffer(self) -> Any:
        width, height = self.framebuffer_size()

        if self._window_fb_handle is None and self._graphics is not None:
            self._window_fb_handle = self._graphics.create_external_framebuffer(0, width, height)
        elif self._window_fb_handle is not None:
            self._window_fb_handle.set_external_target(0, width, height)

        return self._window_fb_handle

    def set_graphics(self, graphics: OpenGLGraphicsBackend) -> None:
        """Set graphics backend for framebuffer creation."""
        self._graphics = graphics

    def get_window_id(self) -> int:
        """Get SDL window ID for event routing."""
        if self._window is None:
            return 0
        return video.SDL_GetWindowID(self._window)

    def blit_from_pass(
        self,
        fb,
        graphics,
        width: int,
        height: int,
        depth_callback=None,
    ) -> None:
        """
        Blit framebuffer texture to this window.

        Called from C++ ColorPass during debug mode to show intermediate
        render state in the debugger window.

        Args:
            fb: Source FramebufferHandle
            graphics: GraphicsBackend for GL operations
            width: Source framebuffer width
            height: Source framebuffer height
            depth_callback: Optional callback to receive depth buffer
        """
        from termin.visualization.render.framegraph.passes.present import (
            PresentToScreenPass,
            _get_texture_from_resource,
        )

        # Capture depth buffer before switching context
        if depth_callback is not None:
            depth = graphics.read_depth_buffer(fb)
            if depth is not None:
                depth_callback(depth)

        # Get texture from FBO
        tex = _get_texture_from_resource(fb)
        if tex is None:
            return

        # Save current context
        saved_context = video.SDL_GL_GetCurrentContext()
        saved_window = video.SDL_GL_GetCurrentWindow()

        # Switch to debugger window context
        self.make_current()

        # Get debugger window size
        dst_w, dst_h = self.framebuffer_size()

        # Bind framebuffer 0 (window)
        graphics.bind_framebuffer(None)
        graphics.set_viewport(0, 0, dst_w, dst_h)

        graphics.set_depth_test(False)
        graphics.set_depth_mask(False)

        # Render fullscreen quad with texture
        shader = PresentToScreenPass._get_shader()
        shader.ensure_ready(graphics)
        shader.use()
        shader.set_uniform_int("u_tex", 0)
        tex.bind(0)
        graphics.draw_ui_textured_quad(0)

        graphics.set_depth_test(True)
        graphics.set_depth_mask(True)

        # Swap buffers
        self.swap_buffers()

        # Restore original context
        if saved_window and saved_context:
            video.SDL_GL_MakeCurrent(saved_window, saved_context)
            # Restore FBO and viewport
            graphics.bind_framebuffer(fb)
            graphics.set_viewport(0, 0, width, height)

    def check_resize(self) -> None:
        """Check if window was resized and call callback if needed."""
        new_w, new_h = self.framebuffer_size()
        if (new_w, new_h) != (self._last_width, self._last_height):
            self._last_width = new_w
            self._last_height = new_h
            if self._framebuffer_size_callback is not None:
                self._framebuffer_size_callback(self, new_w, new_h)
            self._needs_render = True

    def handle_event(self, event: sdl2.SDL_Event) -> None:
        """Process SDL event for this window."""
        event_type = event.type

        if event_type == sdl2.SDL_QUIT:
            self._should_close = True

        elif event_type == sdl2.SDL_WINDOWEVENT:
            window_event = event.window.event
            if window_event == video.SDL_WINDOWEVENT_CLOSE:
                self._should_close = True
            elif window_event in (
                video.SDL_WINDOWEVENT_RESIZED,
                video.SDL_WINDOWEVENT_SIZE_CHANGED,
            ):
                self.check_resize()
            elif window_event == video.SDL_WINDOWEVENT_EXPOSED:
                self._needs_render = True

        elif event_type == sdl2.SDL_MOUSEMOTION:
            if self._cursor_pos_callback is not None:
                self._cursor_pos_callback(
                    self, float(event.motion.x), float(event.motion.y)
                )

        elif event_type == sdl2.SDL_MOUSEWHEEL:
            if self._scroll_callback is not None:
                # Use tracked modifier state (updated via Qt key events)
                mods = self.get_tracked_mods()
                self._scroll_callback(
                    self, float(event.wheel.x), float(event.wheel.y), mods
                )

        elif event_type == sdl2.SDL_MOUSEBUTTONDOWN:
            # Request focus from Qt when clicking on SDL window
            if self._focus_callback is not None:
                self._focus_callback()
            if self._mouse_button_callback is not None:
                button = _translate_mouse_button(event.button.button)
                mods = _translate_sdl_mods(sdl2.SDL_GetModState())
                self._mouse_button_callback(self, button, Action.PRESS, mods)

        elif event_type == sdl2.SDL_MOUSEBUTTONUP:
            if self._mouse_button_callback is not None:
                button = _translate_mouse_button(event.button.button)
                mods = _translate_sdl_mods(sdl2.SDL_GetModState())
                self._mouse_button_callback(self, button, Action.RELEASE, mods)

        elif event_type == sdl2.SDL_KEYDOWN:
            from termin._native import log
            key = _translate_key(event.key.keysym.scancode)
            action = Action.REPEAT if event.key.repeat else Action.PRESS
            mods = _translate_sdl_mods(event.key.keysym.mod)
            log.info(f"[SDL] KEYDOWN: key={key}, mods={mods}")
            if self._key_callback is not None:
                self._key_callback(self, key, event.key.keysym.scancode, action, mods)

        elif event_type == sdl2.SDL_KEYUP:
            from termin._native import log
            key = _translate_key(event.key.keysym.scancode)
            mods = _translate_sdl_mods(event.key.keysym.mod)
            log.info(f"[SDL] KEYUP: key={key}, mods={mods}")
            if self._key_callback is not None:
                self._key_callback(
                    self, key, event.key.keysym.scancode, Action.RELEASE, mods
                )


class SDLEmbeddedWindowBackend(WindowBackend):
    """SDL2 backend for creating windows embeddable in Qt."""

    def __init__(self, graphics: Optional[OpenGLGraphicsBackend] = None):
        _ensure_sdl()
        self._windows: dict[int, SDLEmbeddedWindowHandle] = {}
        self._primary_window: Optional[SDLEmbeddedWindowHandle] = None
        self._graphics = graphics

    def set_graphics(self, graphics: OpenGLGraphicsBackend) -> None:
        """Set graphics backend for new windows."""
        self._graphics = graphics

    def create_embedded_window(
        self, width: int = 800, height: int = 600, title: str = "SDL Viewport"
    ) -> SDLEmbeddedWindowHandle:
        """
        Create SDL window with OpenGL context.

        Returns window that can be embedded into Qt via its native_handle property.
        First window becomes the primary; subsequent windows share its GL context.
        """
        # Share context with primary window if it exists
        share_context = None
        if self._primary_window is not None:
            share_context = self._primary_window._gl_context
            # Make primary context current before creating shared context
            self._primary_window.make_current()

        window = SDLEmbeddedWindowHandle(
            width, height, title,
            share_context=share_context,
            graphics=self._graphics,
        )
        self._windows[window.get_window_id()] = window

        # First window becomes the primary
        if self._primary_window is None:
            self._primary_window = window

        return window

    def create_window(
        self,
        width: int,
        height: int,
        title: str,
        share: Optional[BackendWindow] = None,
    ) -> SDLEmbeddedWindowHandle:
        """Create window (for WindowBackend interface compatibility)."""
        return self.create_embedded_window(width, height, title)

    def poll_events(self) -> None:
        event = sdl2.SDL_Event()
        while sdl2.SDL_PollEvent(ctypes.byref(event)) != 0:
            # Route event to appropriate window
            window_id = 0

            if event.type == sdl2.SDL_WINDOWEVENT:
                window_id = event.window.windowID
            elif event.type in (
                sdl2.SDL_MOUSEMOTION,
                sdl2.SDL_MOUSEBUTTONDOWN,
                sdl2.SDL_MOUSEBUTTONUP,
                sdl2.SDL_MOUSEWHEEL,
            ):
                window_id = event.motion.windowID
            elif event.type in (sdl2.SDL_KEYDOWN, sdl2.SDL_KEYUP):
                window_id = event.key.windowID
            elif event.type == sdl2.SDL_QUIT:
                for win in self._windows.values():
                    win.handle_event(event)
                continue

            if window_id in self._windows:
                self._windows[window_id].handle_event(event)

    def remove_window(self, window: SDLEmbeddedWindowHandle) -> None:
        """Remove window from tracking."""
        window_id = window.get_window_id()
        if window_id in self._windows:
            del self._windows[window_id]

    def terminate(self) -> None:
        for win in list(self._windows.values()):
            win.close()
        self._windows.clear()
        # Don't call SDL_Quit here - Qt might still need the display
