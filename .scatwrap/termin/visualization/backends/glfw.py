<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/backends/glfw.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;GLFW-based window backend.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
from typing import Callable, Optional<br>
<br>
import glfw<br>
<br>
from .base import Action, BackendWindow, Key, MouseButton, WindowBackend<br>
<br>
from OpenGL import GL as gl<br>
<br>
<br>
def _ensure_glfw():<br>
&#9;if not glfw.init():<br>
&#9;&#9;raise RuntimeError(&quot;Failed to initialize GLFW&quot;)<br>
<br>
<br>
def _translate_mouse_button(button: int) -&gt; MouseButton:<br>
&#9;mapping = {<br>
&#9;&#9;glfw.MOUSE_BUTTON_LEFT: MouseButton.LEFT,<br>
&#9;&#9;glfw.MOUSE_BUTTON_RIGHT: MouseButton.RIGHT,<br>
&#9;&#9;glfw.MOUSE_BUTTON_MIDDLE: MouseButton.MIDDLE,<br>
&#9;}<br>
&#9;return mapping.get(button, MouseButton.LEFT)<br>
<br>
<br>
def _translate_action(action: int) -&gt; Action:<br>
&#9;mapping = {<br>
&#9;&#9;glfw.PRESS: Action.PRESS,<br>
&#9;&#9;glfw.RELEASE: Action.RELEASE,<br>
&#9;&#9;glfw.REPEAT: Action.REPEAT,<br>
&#9;}<br>
&#9;return mapping.get(action, Action.RELEASE)<br>
<br>
<br>
def _translate_key(key: int) -&gt; Key:<br>
&#9;if key == glfw.KEY_ESCAPE:<br>
&#9;&#9;return Key.ESCAPE<br>
&#9;if key == glfw.KEY_SPACE:<br>
&#9;&#9;return Key.SPACE<br>
&#9;if key &lt; 0:<br>
&#9;&#9;return Key.UNKNOWN<br>
&#9;try:<br>
&#9;&#9;return Key(key)<br>
&#9;except ValueError:<br>
&#9;&#9;return Key.UNKNOWN<br>
<br>
<br>
class GLFWWindowHandle(BackendWindow):<br>
&#9;def __init__(self, width: int, height: int, title: str, share: Optional[BackendWindow] = None):<br>
&#9;&#9;_ensure_glfw()<br>
&#9;&#9;glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)<br>
&#9;&#9;glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)<br>
&#9;&#9;glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)<br>
&#9;&#9;glfw.window_hint(glfw.RESIZABLE, glfw.TRUE)<br>
<br>
&#9;&#9;share_handle = share._window if isinstance(share, GLFWWindowHandle) else getattr(share, &quot;_window&quot;, None)<br>
&#9;&#9;self._window = glfw.create_window(width, height, title, None, share_handle)<br>
&#9;&#9;if not self._window:<br>
&#9;&#9;&#9;raise RuntimeError(&quot;Failed to create GLFW window&quot;)<br>
&#9;&#9;glfw.make_context_current(self._window)<br>
<br>
&#9;def close(self):<br>
&#9;&#9;if self._window:<br>
&#9;&#9;&#9;glfw.destroy_window(self._window)<br>
&#9;&#9;&#9;self._window = None<br>
<br>
&#9;def should_close(self) -&gt; bool:<br>
&#9;&#9;return self._window is None or glfw.window_should_close(self._window)<br>
<br>
&#9;def make_current(self):<br>
&#9;&#9;if self._window is not None:<br>
&#9;&#9;&#9;glfw.make_context_current(self._window)<br>
<br>
&#9;def swap_buffers(self):<br>
&#9;&#9;if self._window is not None:<br>
&#9;&#9;&#9;glfw.swap_buffers(self._window)<br>
<br>
&#9;def framebuffer_size(self):<br>
&#9;&#9;return glfw.get_framebuffer_size(self._window)<br>
<br>
&#9;def window_size(self):<br>
&#9;&#9;return glfw.get_window_size(self._window)<br>
<br>
&#9;def get_cursor_pos(self):<br>
&#9;&#9;return glfw.get_cursor_pos(self._window)<br>
<br>
&#9;def set_should_close(self, flag: bool):<br>
&#9;&#9;if self._window is not None:<br>
&#9;&#9;&#9;glfw.set_window_should_close(self._window, flag)<br>
<br>
&#9;def set_user_pointer(self, ptr):<br>
&#9;&#9;glfw.set_window_user_pointer(self._window, ptr)<br>
<br>
&#9;def set_framebuffer_size_callback(self, callback: Callable):<br>
&#9;&#9;glfw.set_framebuffer_size_callback(self._window, lambda *_args: callback(self, *_args[1:]))<br>
<br>
&#9;def set_cursor_pos_callback(self, callback: Callable):<br>
&#9;&#9;def wrapper(_win, x, y):<br>
&#9;&#9;&#9;callback(self, x, y)<br>
&#9;&#9;glfw.set_cursor_pos_callback(self._window, wrapper)<br>
<br>
&#9;def set_scroll_callback(self, callback: Callable):<br>
&#9;&#9;def wrapper(_win, xoffset, yoffset):<br>
&#9;&#9;&#9;callback(self, xoffset, yoffset)<br>
&#9;&#9;glfw.set_scroll_callback(self._window, wrapper)<br>
<br>
&#9;def set_mouse_button_callback(self, callback: Callable):<br>
&#9;&#9;def wrapper(_win, button, action, mods):<br>
&#9;&#9;&#9;callback(self, _translate_mouse_button(button), _translate_action(action), mods)<br>
&#9;&#9;glfw.set_mouse_button_callback(self._window, wrapper)<br>
<br>
&#9;def set_key_callback(self, callback: Callable):<br>
&#9;&#9;def wrapper(_win, key, scancode, action, mods):<br>
&#9;&#9;&#9;callback(self, _translate_key(key), scancode, _translate_action(action), mods)<br>
&#9;&#9;glfw.set_key_callback(self._window, wrapper)<br>
<br>
&#9;def request_update(self):<br>
&#9;&#9;# GLFW не имеет встроенного механизма для запроса перерисовки окна,<br>
&#9;&#9;# обычно это делается в основном цикле приложения.<br>
&#9;&#9;pass<br>
<br>
&#9;def bind_window_framebuffer(self):<br>
&#9;&#9;gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)<br>
<br>
<br>
class GLFWWindowBackend(WindowBackend):<br>
&#9;def __init__(self):<br>
&#9;&#9;_ensure_glfw()<br>
<br>
&#9;def create_window(self, width: int, height: int, title: str, share: Optional[BackendWindow] = None) -&gt; GLFWWindowHandle:<br>
&#9;&#9;return GLFWWindowHandle(width, height, title, share=share)<br>
<br>
&#9;def poll_events(self):<br>
&#9;&#9;glfw.poll_events()<br>
<br>
&#9;def terminate(self):<br>
&#9;&#9;glfw.terminate()<br>
<!-- END SCAT CODE -->
</body>
</html>
