"""SDL2-based window backend using C++ implementation."""

from __future__ import annotations

from typing import Any, Callable, Optional, Tuple

from termin._native.platform import (
    SDLWindow,
    SDLWindowBackend as _SDLWindowBackend,
)
from termin._native.render import OpenGLGraphicsBackend

from .base import Action, BackendWindow, Key, MouseButton, WindowBackend


def _translate_mouse_button(button: int) -> MouseButton:
    """Convert C++ button constant to Python enum."""
    if button == SDLWindow.MOUSE_BUTTON_LEFT:
        return MouseButton.LEFT
    elif button == SDLWindow.MOUSE_BUTTON_RIGHT:
        return MouseButton.RIGHT
    elif button == SDLWindow.MOUSE_BUTTON_MIDDLE:
        return MouseButton.MIDDLE
    return MouseButton.LEFT


def _translate_action(action: int) -> Action:
    """Convert C++ action constant to Python enum."""
    if action == SDLWindow.ACTION_RELEASE:
        return Action.RELEASE
    elif action == SDLWindow.ACTION_PRESS:
        return Action.PRESS
    elif action == SDLWindow.ACTION_REPEAT:
        return Action.REPEAT
    return Action.PRESS


def _translate_key(keycode: int) -> Key:
    """Convert SDL keycode to Python Key enum."""
    # Special keys
    if keycode == 27:  # SDLK_ESCAPE
        return Key.ESCAPE
    if keycode == 32:  # SDLK_SPACE
        return Key.SPACE
    # ASCII keys
    if 0 <= keycode < 128:
        try:
            return Key(keycode)
        except ValueError:
            pass
    return Key.UNKNOWN


class SDLWindowHandle(BackendWindow):
    """SDL2 window wrapper using C++ SDLWindow."""

    def __init__(
        self,
        width: int,
        height: int,
        title: str,
        share: Optional[BackendWindow] = None,
        graphics: Optional[OpenGLGraphicsBackend] = None,
    ):
        share_win = None
        if share is not None and isinstance(share, SDLWindowHandle):
            share_win = share._window

        self._window = SDLWindow(width, height, title, share_win)

        if graphics is not None:
            self._window.set_graphics(graphics)

        # Python callbacks
        self._py_framebuffer_size_callback: Optional[Callable] = None
        self._py_cursor_pos_callback: Optional[Callable] = None
        self._py_scroll_callback: Optional[Callable] = None
        self._py_mouse_button_callback: Optional[Callable] = None
        self._py_key_callback: Optional[Callable] = None

        self._user_pointer: Any = None

    def close(self) -> None:
        self._window.close()

    def should_close(self) -> bool:
        return self._window.should_close()

    def make_current(self) -> None:
        self._window.make_current()

    def swap_buffers(self) -> None:
        self._window.swap_buffers()

    def framebuffer_size(self) -> Tuple[int, int]:
        return self._window.framebuffer_size()

    def window_size(self) -> Tuple[int, int]:
        return self._window.window_size()

    def get_cursor_pos(self) -> Tuple[float, float]:
        return self._window.get_cursor_pos()

    def set_should_close(self, flag: bool) -> None:
        self._window.set_should_close(flag)

    def set_user_pointer(self, ptr: Any) -> None:
        self._user_pointer = ptr

    def set_graphics(self, graphics: OpenGLGraphicsBackend) -> None:
        """Set graphics backend for framebuffer creation."""
        self._window.set_graphics(graphics)

    def set_framebuffer_size_callback(self, callback: Callable) -> None:
        self._py_framebuffer_size_callback = callback
        if callback is None:
            self._window.set_framebuffer_size_callback(None)
        else:
            def wrapper(win, w, h):
                callback(self, w, h)
            self._window.set_framebuffer_size_callback(wrapper)

    def set_cursor_pos_callback(self, callback: Callable) -> None:
        self._py_cursor_pos_callback = callback
        if callback is None:
            self._window.set_cursor_pos_callback(None)
        else:
            def wrapper(win, x, y):
                callback(self, x, y)
            self._window.set_cursor_pos_callback(wrapper)

    def set_scroll_callback(self, callback: Callable) -> None:
        self._py_scroll_callback = callback
        if callback is None:
            self._window.set_scroll_callback(None)
        else:
            def wrapper(win, x, y):
                callback(self, x, y)
            self._window.set_scroll_callback(wrapper)

    def set_mouse_button_callback(self, callback: Callable) -> None:
        self._py_mouse_button_callback = callback
        if callback is None:
            self._window.set_mouse_button_callback(None)
        else:
            def wrapper(win, button, action, mods):
                py_button = _translate_mouse_button(button)
                py_action = _translate_action(action)
                callback(self, py_button, py_action, mods)
            self._window.set_mouse_button_callback(wrapper)

    def set_key_callback(self, callback: Callable) -> None:
        self._py_key_callback = callback
        if callback is None:
            self._window.set_key_callback(None)
        else:
            def wrapper(win, key, scancode, action, mods):
                py_key = _translate_key(key)
                py_action = _translate_action(action)
                callback(self, py_key, scancode, py_action, mods)
            self._window.set_key_callback(wrapper)

    def request_update(self) -> None:
        pass  # SDL uses pull model

    def get_window_framebuffer(self) -> Any:
        return self._window.get_window_framebuffer()

    def get_window_id(self) -> int:
        return self._window.get_window_id()


class SDLWindowBackend(WindowBackend):
    """SDL2 window backend using C++ implementation."""

    def __init__(self, graphics: Optional[OpenGLGraphicsBackend] = None):
        self._backend = _SDLWindowBackend()
        self._graphics = graphics
        self._windows: dict[int, SDLWindowHandle] = {}

    def set_graphics(self, graphics: OpenGLGraphicsBackend) -> None:
        """Set graphics backend for new windows."""
        self._graphics = graphics

    def create_window(
        self,
        width: int,
        height: int,
        title: str,
        share: Optional[BackendWindow] = None,
    ) -> SDLWindowHandle:
        window = SDLWindowHandle(
            width, height, title,
            share=share,
            graphics=self._graphics,
        )
        self._windows[window.get_window_id()] = window
        return window

    def poll_events(self) -> None:
        self._backend.poll_events()

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
        self._backend.terminate()
