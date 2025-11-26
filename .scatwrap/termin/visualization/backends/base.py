<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/backends/base.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Backend interfaces decoupling rendering/window code from specific libraries.&quot;&quot;&quot;<br>
<br>
from __future__ import annotations<br>
<br>
from abc import ABC, abstractmethod<br>
from enum import IntEnum<br>
from typing import Any, Callable, Optional, Tuple<br>
<br>
<br>
class Action(IntEnum):<br>
&#9;RELEASE = 0<br>
&#9;PRESS = 1<br>
&#9;REPEAT = 2<br>
<br>
<br>
class MouseButton(IntEnum):<br>
&#9;LEFT = 0<br>
&#9;RIGHT = 1<br>
&#9;MIDDLE = 2<br>
<br>
<br>
class Key(IntEnum):<br>
&#9;UNKNOWN = -1<br>
&#9;SPACE = 32<br>
&#9;ESCAPE = 256<br>
<br>
<br>
class ShaderHandle(ABC):<br>
&#9;&quot;&quot;&quot;Backend-specific shader program.&quot;&quot;&quot;<br>
<br>
&#9;@abstractmethod<br>
&#9;def use(self):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def stop(self):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def delete(self):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_uniform_matrix4(self, name: str, matrix):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_uniform_vec3(self, name: str, vector):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_uniform_vec4(self, name: str, vector):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_uniform_float(self, name: str, value: float):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_uniform_int(self, name: str, value: int):<br>
&#9;&#9;...<br>
<br>
<br>
class MeshHandle(ABC):<br>
&#9;&quot;&quot;&quot;Backend mesh buffers ready for drawing.&quot;&quot;&quot;<br>
<br>
&#9;@abstractmethod<br>
&#9;def draw(self):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def delete(self):<br>
&#9;&#9;...<br>
<br>
<br>
class PolylineHandle(ABC):<br>
&#9;&quot;&quot;&quot;Backend polyline buffers.&quot;&quot;&quot;<br>
<br>
&#9;@abstractmethod<br>
&#9;def draw(self):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def delete(self):<br>
&#9;&#9;...<br>
<br>
<br>
class TextureHandle(ABC):<br>
&#9;&quot;&quot;&quot;Backend texture object.&quot;&quot;&quot;<br>
<br>
&#9;@abstractmethod<br>
&#9;def bind(self, unit: int = 0):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def delete(self):<br>
&#9;&#9;...<br>
<br>
class FramebufferHandle(ABC):<br>
&#9;&quot;&quot;&quot;Offscreen framebuffer with a color attachment texture.&quot;&quot;&quot;<br>
<br>
&#9;@abstractmethod<br>
&#9;def resize(self, size: Tuple[int, int]):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def color_texture(self) -&gt; TextureHandle:<br>
&#9;&#9;&quot;&quot;&quot;TextureHandle for color attachment.&quot;&quot;&quot;<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def delete(self):<br>
&#9;&#9;...<br>
<br>
<br>
class GraphicsBackend(ABC):<br>
&#9;&quot;&quot;&quot;Abstract graphics backend (OpenGL, Vulkan, etc.).&quot;&quot;&quot;<br>
<br>
&#9;@abstractmethod<br>
&#9;def ensure_ready(self):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_viewport(self, x: int, y: int, w: int, h: int):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def enable_scissor(self, x: int, y: int, w: int, h: int):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def disable_scissor(self):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def clear_color_depth(self, color):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_depth_test(self, enabled: bool):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_depth_mask(self, enabled: bool):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_depth_func(self, func: str):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_cull_face(self, enabled: bool):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_blend(self, enabled: bool):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_blend_func(self, src: str, dst: str):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def create_shader(self, vertex_source: str, fragment_source: str, geometry_source: str | None = None) -&gt; ShaderHandle:<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def create_mesh(self, mesh) -&gt; MeshHandle:<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def create_polyline(self, polyline) -&gt; PolylineHandle:<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def create_texture(self, image_data, size: Tuple[int, int], channels: int = 4, mipmap: bool = True, clamp: bool = False) -&gt; TextureHandle:<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def draw_ui_vertices(self, context_key: int, vertices):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def draw_ui_textured_quad(self, context_key: int):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_polygon_mode(self, mode: str):  # &quot;fill&quot; / &quot;line&quot;<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_cull_face_enabled(self, enabled: bool):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_depth_test_enabled(self, enabled: bool):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_depth_write_enabled(self, enabled: bool):<br>
&#9;&#9;...<br>
<br>
&#9;def apply_render_state(self, state: RenderState):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Применяет полное состояние рендера.<br>
&#9;&#9;Все значения — абсолютные, без &quot;оставь как было&quot;.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;self.set_polygon_mode(state.polygon_mode)<br>
&#9;&#9;self.set_cull_face(state.cull)<br>
&#9;&#9;self.set_depth_test(state.depth_test)<br>
&#9;&#9;self.set_depth_mask(state.depth_write)<br>
&#9;&#9;self.set_blend(state.blend)<br>
&#9;&#9;if state.blend:<br>
&#9;&#9;&#9;self.set_blend_func(state.blend_src, state.blend_dst)<br>
<br>
&#9;@abstractmethod<br>
&#9;def read_pixel(self, framebuffer, x: int, y: int):<br>
&#9;&#9;&quot;&quot;&quot;Вернуть (r,g,b,a) в [0,1] из указанного FBO.&quot;&quot;&quot;<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def create_framebuffer(self, size: Tuple[int, int]) -&gt; &quot;FramebufferHandle&quot;:<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def bind_framebuffer(self, framebuffer: &quot;FramebufferHandle | None&quot;):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Bind custom framebuffer or default (if None).<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;...<br>
<br>
<br>
class BackendWindow(ABC):<br>
&#9;&quot;&quot;&quot;Abstract window wrapper.&quot;&quot;&quot;<br>
<br>
&#9;@abstractmethod<br>
&#9;def bind_window_framebuffer(self):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def close(self):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def should_close(self) -&gt; bool:<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def make_current(self):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def swap_buffers(self):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def framebuffer_size(self) -&gt; Tuple[int, int]:<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def window_size(self) -&gt; Tuple[int, int]:<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def get_cursor_pos(self) -&gt; Tuple[float, float]:<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_should_close(self, flag: bool):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_user_pointer(self, ptr: Any):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_framebuffer_size_callback(self, callback: Callable):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_cursor_pos_callback(self, callback: Callable):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_scroll_callback(self, callback: Callable):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_mouse_button_callback(self, callback: Callable):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def set_key_callback(self, callback: Callable):<br>
&#9;&#9;...<br>
<br>
&#9;def drives_render(self) -&gt; bool:<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Возвращает True, если рендер вызывается бекэндом самостоятельно (например, Qt виджет),<br>
&#9;&#9;и False, если движок сам вызывает render() каждый кадр (например, GLFW).<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return False<br>
<br>
&#9;<br>
&#9;@abstractmethod<br>
&#9;def request_update(self):<br>
&#9;&#9;...<br>
<br>
<br>
class WindowBackend(ABC):<br>
&#9;&quot;&quot;&quot;Abstract window backend (GLFW, SDL, etc.).&quot;&quot;&quot;<br>
<br>
&#9;@abstractmethod<br>
&#9;def create_window(self, width: int, height: int, title: str, share: Optional[Any] = None) -&gt; BackendWindow:<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def poll_events(self):<br>
&#9;&#9;...<br>
<br>
&#9;@abstractmethod<br>
&#9;def terminate(self):<br>
&#9;&#9;...<br>
<br>
<!-- END SCAT CODE -->
</body>
</html>
