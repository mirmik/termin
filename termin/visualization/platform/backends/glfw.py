"""GLFW-based window backend."""

from __future__ import annotations

from typing import Callable, Optional

import glfw

from .base import Action, BackendWindow, Key, MouseButton, WindowBackend

from OpenGL import GL as gl


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
    def __init__(self, width: int, height: int, title: str, share: Optional[BackendWindow] = None):
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
            callback(self, xoffset, yoffset)
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
        # GLFW не имеет встроенного механизма для запроса перерисовки окна,
        # обычно это делается в основном цикле приложения.
        pass

    def get_window_framebuffer(self):
        width, height = self.framebuffer_size()
        from termin.visualization.render.opengl.backends import OpenGLFramebufferHandle

        fb = getattr(self, "_window_fb_handle", None)
        if fb is None:
            fb = OpenGLFramebufferHandle((width, height), fbo_id=0, owns_attachments=False)
            self._window_fb_handle = fb
        else:
            fb.set_external_target(0, (width, height))

        return fb


class GLFWWindowBackend(WindowBackend):
    def __init__(self):
        _ensure_glfw()

    def create_window(self, width: int, height: int, title: str, share: Optional[BackendWindow] = None) -> GLFWWindowHandle:
        return GLFWWindowHandle(width, height, title, share=share)

    def poll_events(self):
        glfw.poll_events()

    def terminate(self):
        glfw.terminate()
