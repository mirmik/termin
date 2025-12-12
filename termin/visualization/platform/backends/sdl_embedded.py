"""SDL2 backend for embedding into Qt widgets.

Creates a standalone SDL+OpenGL window and embeds it into Qt layout
using QWindow.fromWinId() + QWidget.createWindowContainer().
"""

from __future__ import annotations

import ctypes
import sys
from typing import Any, Callable, Optional, Tuple

import sdl2
from sdl2 import video

from .base import Action, BackendWindow, Key, MouseButton, WindowBackend


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

    def __init__(self, width: int = 800, height: int = 600, title: str = "SDL Viewport"):
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

        result = video.SDL_GL_MakeCurrent(self._window, self._gl_context)
        print(f"SDL: Window created, GL context: {self._gl_context}, make_current result: {result}")

        # Disable VSync - we control frame rate ourselves
        video.SDL_GL_SetSwapInterval(0)

        # Get native handle for Qt embedding
        self._native_handle = _get_native_window_handle(self._window)
        print(f"SDL: Native handle: {self._native_handle}")

        # Callbacks
        self._framebuffer_size_callback: Optional[Callable] = None
        self._cursor_pos_callback: Optional[Callable] = None
        self._scroll_callback: Optional[Callable] = None
        self._mouse_button_callback: Optional[Callable] = None
        self._key_callback: Optional[Callable] = None

        self._user_pointer: Any = None
        self._should_close = False
        self._needs_render = True

        # Cache for window framebuffer handle
        self._window_fb_handle: Optional[Any] = None

        # Last known size for resize detection
        self._last_width = width
        self._last_height = height

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
            result = video.SDL_GL_MakeCurrent(self._window, self._gl_context)
            if result != 0:
                print(f"SDL_GL_MakeCurrent failed: {sdl2.SDL_GetError()}")

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
        from termin.visualization.platform.backends.opengl import OpenGLFramebufferHandle

        if self._window_fb_handle is None:
            self._window_fb_handle = OpenGLFramebufferHandle(
                (width, height), fbo_id=0, owns_attachments=False
            )
        else:
            self._window_fb_handle.set_external_target(0, (width, height))

        return self._window_fb_handle

    def get_window_id(self) -> int:
        """Get SDL window ID for event routing."""
        if self._window is None:
            return 0
        return video.SDL_GetWindowID(self._window)

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
                self._scroll_callback(
                    self, float(event.wheel.x), float(event.wheel.y)
                )

        elif event_type == sdl2.SDL_MOUSEBUTTONDOWN:
            if self._mouse_button_callback is not None:
                button = _translate_mouse_button(event.button.button)
                self._mouse_button_callback(self, button, Action.PRESS, 0)

        elif event_type == sdl2.SDL_MOUSEBUTTONUP:
            if self._mouse_button_callback is not None:
                button = _translate_mouse_button(event.button.button)
                self._mouse_button_callback(self, button, Action.RELEASE, 0)

        elif event_type == sdl2.SDL_KEYDOWN:
            if self._key_callback is not None:
                key = _translate_key(event.key.keysym.scancode)
                action = Action.REPEAT if event.key.repeat else Action.PRESS
                self._key_callback(self, key, event.key.keysym.scancode, action, 0)

        elif event_type == sdl2.SDL_KEYUP:
            if self._key_callback is not None:
                key = _translate_key(event.key.keysym.scancode)
                self._key_callback(
                    self, key, event.key.keysym.scancode, Action.RELEASE, 0
                )


class SDLEmbeddedWindowBackend(WindowBackend):
    """SDL2 backend for creating windows embeddable in Qt."""

    def __init__(self):
        _ensure_sdl()
        self._windows: dict[int, SDLEmbeddedWindowHandle] = {}

    def create_embedded_window(
        self, width: int = 800, height: int = 600, title: str = "SDL Viewport"
    ) -> SDLEmbeddedWindowHandle:
        """
        Create SDL window with OpenGL context.

        Returns window that can be embedded into Qt via its native_handle property.
        """
        window = SDLEmbeddedWindowHandle(width, height, title)
        self._windows[window.get_window_id()] = window
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
