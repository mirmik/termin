"""SDL2-based window backend."""

from __future__ import annotations

from typing import Any, Callable, Optional, Tuple

import ctypes

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
    # Map ASCII keys directly if possible
    keycode = sdl2.SDL_GetKeyFromScancode(scancode)
    if 0 <= keycode < 128:
        try:
            return Key(keycode)
        except ValueError:
            pass
    return Key.UNKNOWN


class SDLWindowHandle(BackendWindow):
    """SDL2 window with OpenGL context."""

    def __init__(
        self,
        width: int,
        height: int,
        title: str,
        share: Optional[BackendWindow] = None,
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

        flags = (
            video.SDL_WINDOW_OPENGL
            | video.SDL_WINDOW_RESIZABLE
            | video.SDL_WINDOW_SHOWN
        )

        self._window = video.SDL_CreateWindow(
            title.encode("utf-8"),
            video.SDL_WINDOWPOS_CENTERED,
            video.SDL_WINDOWPOS_CENTERED,
            width,
            height,
            flags,
        )

        if not self._window:
            raise RuntimeError(f"Failed to create SDL window: {sdl2.SDL_GetError()}")

        # Share context if provided
        if share is not None and isinstance(share, SDLWindowHandle):
            video.SDL_GL_SetAttribute(video.SDL_GL_SHARE_WITH_CURRENT_CONTEXT, 1)
            share.make_current()

        self._gl_context = video.SDL_GL_CreateContext(self._window)
        if not self._gl_context:
            video.SDL_DestroyWindow(self._window)
            raise RuntimeError(f"Failed to create GL context: {sdl2.SDL_GetError()}")

        video.SDL_GL_MakeCurrent(self._window, self._gl_context)

        # Callbacks
        self._framebuffer_size_callback: Optional[Callable] = None
        self._cursor_pos_callback: Optional[Callable] = None
        self._scroll_callback: Optional[Callable] = None
        self._mouse_button_callback: Optional[Callable] = None
        self._key_callback: Optional[Callable] = None

        self._user_pointer: Any = None
        self._should_close = False

        # Cache for window framebuffer handle
        self._window_fb_handle: Optional[Any] = None

        # Last known size for resize detection
        self._last_width = width
        self._last_height = height

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

    def request_update(self) -> None:
        # SDL uses pull model, no explicit update request needed
        pass

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

    def _handle_event(self, event: sdl2.SDL_Event) -> None:
        """Process SDL event for this window."""
        event_type = event.type

        if event_type == sdl2.SDL_QUIT:
            self._should_close = True

        elif event_type == sdl2.SDL_WINDOWEVENT:
            window_event = event.window.event
            if window_event == video.SDL_WINDOWEVENT_CLOSE:
                self._should_close = True
            elif window_event == video.SDL_WINDOWEVENT_RESIZED:
                new_w, new_h = self.framebuffer_size()
                if (new_w, new_h) != (self._last_width, self._last_height):
                    self._last_width = new_w
                    self._last_height = new_h
                    if self._framebuffer_size_callback is not None:
                        self._framebuffer_size_callback(self, new_w, new_h)

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


class SDLWindowBackend(WindowBackend):
    """SDL2 window backend."""

    def __init__(self):
        _ensure_sdl()
        self._windows: dict[int, SDLWindowHandle] = {}

    def create_window(
        self,
        width: int,
        height: int,
        title: str,
        share: Optional[BackendWindow] = None,
    ) -> SDLWindowHandle:
        window = SDLWindowHandle(width, height, title, share=share)
        self._windows[window.get_window_id()] = window
        return window

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
                # Quit event goes to all windows
                for win in self._windows.values():
                    win._handle_event(event)
                continue

            if window_id in self._windows:
                self._windows[window_id]._handle_event(event)

        # Clean up closed windows
        closed_ids = [
            wid for wid, win in self._windows.items() if win.should_close()
        ]
        for wid in closed_ids:
            del self._windows[wid]

    def terminate(self) -> None:
        for win in list(self._windows.values()):
            win.close()
        self._windows.clear()
        sdl2.SDL_Quit()
