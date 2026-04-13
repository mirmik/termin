"""GLFW-based window backend."""

from __future__ import annotations

from typing import Callable, Optional

import glfw

from tcbase import Action, Key, MouseButton
from tgfx.window import BackendWindow, WindowBackend

from termin.graphics import OpenGLGraphicsBackend


def _ensure_glfw():
    if not glfw.init():
        raise RuntimeError("Failed to initialize GLFW")


def _translate_mouse_button(button: int) -> MouseButton:
    mapping = {
        glfw.MOUSE_BUTTON_LEFT: MouseButton.LEFT,
        glfw.MOUSE_BUTTON_RIGHT: MouseButton.RIGHT,
        glfw.MOUSE_BUTTON_MIDDLE: MouseButton.MIDDLE,
    }
    return mapping.get(button, MouseButton.LEFT)


def _translate_action(action: int) -> Action:
    mapping = {
        glfw.PRESS: Action.PRESS,
        glfw.RELEASE: Action.RELEASE,
        glfw.REPEAT: Action.REPEAT,
    }
    return mapping.get(action, Action.RELEASE)


def _translate_key(key: int) -> Key:
    if key == glfw.KEY_ESCAPE:
        return Key.ESCAPE
    if key == glfw.KEY_SPACE:
        return Key.SPACE
    if key < 0:
        return Key.UNKNOWN
    try:
        return Key(key)
    except ValueError:
        return Key.UNKNOWN


class GLFWWindowHandle(BackendWindow):
    def __init__(
        self,
        width: int,
        height: int,
        title: str,
        share: Optional[BackendWindow] = None,
        graphics: Optional[OpenGLGraphicsBackend] = None,
    ):
        _ensure_glfw()
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.RESIZABLE, glfw.TRUE)

        share_handle = share._window if isinstance(share, GLFWWindowHandle) else getattr(share, "_window", None)
        self._window = glfw.create_window(width, height, title, None, share_handle)
        if not self._window:
            raise RuntimeError("Failed to create GLFW window")
        glfw.make_context_current(self._window)

        self._graphics = graphics
        self._window_fb_handle = None

    def close(self):
        if self._window:
            glfw.destroy_window(self._window)
            self._window = None

    def should_close(self) -> bool:
        return self._window is None or glfw.window_should_close(self._window)

    def make_current(self):
        if self._window is not None:
            glfw.make_context_current(self._window)

    def swap_buffers(self):
        if self._window is not None:
            glfw.swap_buffers(self._window)

    def framebuffer_size(self):
        return glfw.get_framebuffer_size(self._window)

    def window_size(self):
        return glfw.get_window_size(self._window)

    def get_cursor_pos(self):
        return glfw.get_cursor_pos(self._window)

    def set_should_close(self, flag: bool):
        if self._window is not None:
            glfw.set_window_should_close(self._window, flag)

    def set_user_pointer(self, ptr):
        glfw.set_window_user_pointer(self._window, ptr)

    def set_framebuffer_size_callback(self, callback: Callable):
        glfw.set_framebuffer_size_callback(self._window, lambda *_args: callback(self, *_args[1:]))

    def set_cursor_pos_callback(self, callback: Callable):
        def wrapper(_win, x, y):
            callback(self, x, y)
        glfw.set_cursor_pos_callback(self._window, wrapper)

    def set_scroll_callback(self, callback: Callable):
        def wrapper(_win, xoffset, yoffset):
            # Query modifier keys since GLFW scroll callback doesn't include mods
            mods = 0
            if glfw.get_key(_win, glfw.KEY_LEFT_SHIFT) == glfw.PRESS or \
               glfw.get_key(_win, glfw.KEY_RIGHT_SHIFT) == glfw.PRESS:
                mods |= 0x0001  # MOD_SHIFT
            if glfw.get_key(_win, glfw.KEY_LEFT_CONTROL) == glfw.PRESS or \
               glfw.get_key(_win, glfw.KEY_RIGHT_CONTROL) == glfw.PRESS:
                mods |= 0x0002  # MOD_CONTROL
            if glfw.get_key(_win, glfw.KEY_LEFT_ALT) == glfw.PRESS or \
               glfw.get_key(_win, glfw.KEY_RIGHT_ALT) == glfw.PRESS:
                mods |= 0x0004  # MOD_ALT
            callback(self, xoffset, yoffset, mods)
        glfw.set_scroll_callback(self._window, wrapper)

    def set_mouse_button_callback(self, callback: Callable):
        def wrapper(_win, button, action, mods):
            callback(self, _translate_mouse_button(button), _translate_action(action), mods)
        glfw.set_mouse_button_callback(self._window, wrapper)

    def set_key_callback(self, callback: Callable):
        def wrapper(_win, key, scancode, action, mods):
            callback(self, _translate_key(key), scancode, _translate_action(action), mods)
        glfw.set_key_callback(self._window, wrapper)

    def request_update(self):
        # GLFW uses pull model
        pass

    def get_window_framebuffer(self):
        width, height = self.framebuffer_size()

        if self._window_fb_handle is None and self._graphics is not None:
            self._window_fb_handle = self._graphics.create_external_framebuffer(0, width, height)
        elif self._window_fb_handle is not None:
            self._window_fb_handle.set_external_target(0, width, height)

        return self._window_fb_handle

    def set_graphics(self, graphics: OpenGLGraphicsBackend) -> None:
        """Set graphics backend for framebuffer creation."""
        self._graphics = graphics


class GLFWWindowBackend(WindowBackend):
    def __init__(self, graphics: Optional[OpenGLGraphicsBackend] = None):
        _ensure_glfw()
        self._graphics = graphics

    def set_graphics(self, graphics: OpenGLGraphicsBackend) -> None:
        """Set graphics backend for new windows."""
        self._graphics = graphics

    def create_window(
        self,
        width: int,
        height: int,
        title: str,
        share: Optional[BackendWindow] = None,
    ) -> GLFWWindowHandle:
        return GLFWWindowHandle(width, height, title, share=share, graphics=self._graphics)

    def poll_events(self):
        glfw.poll_events()

    def terminate(self):
        glfw.terminate()
