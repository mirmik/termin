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
    RELEASE = 0<br>
    PRESS = 1<br>
    REPEAT = 2<br>
<br>
<br>
class MouseButton(IntEnum):<br>
    LEFT = 0<br>
    RIGHT = 1<br>
    MIDDLE = 2<br>
<br>
<br>
class Key(IntEnum):<br>
    UNKNOWN = -1<br>
    SPACE = 32<br>
    ESCAPE = 256<br>
<br>
<br>
class ShaderHandle(ABC):<br>
    &quot;&quot;&quot;Backend-specific shader program.&quot;&quot;&quot;<br>
<br>
    @abstractmethod<br>
    def use(self):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def stop(self):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def delete(self):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_uniform_matrix4(self, name: str, matrix):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_uniform_vec3(self, name: str, vector):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_uniform_vec4(self, name: str, vector):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_uniform_float(self, name: str, value: float):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_uniform_int(self, name: str, value: int):<br>
        ...<br>
<br>
<br>
class MeshHandle(ABC):<br>
    &quot;&quot;&quot;Backend mesh buffers ready for drawing.&quot;&quot;&quot;<br>
<br>
    @abstractmethod<br>
    def draw(self):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def delete(self):<br>
        ...<br>
<br>
<br>
class PolylineHandle(ABC):<br>
    &quot;&quot;&quot;Backend polyline buffers.&quot;&quot;&quot;<br>
<br>
    @abstractmethod<br>
    def draw(self):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def delete(self):<br>
        ...<br>
<br>
<br>
class TextureHandle(ABC):<br>
    &quot;&quot;&quot;Backend texture object.&quot;&quot;&quot;<br>
<br>
    @abstractmethod<br>
    def bind(self, unit: int = 0):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def delete(self):<br>
        ...<br>
<br>
class FramebufferHandle(ABC):<br>
    &quot;&quot;&quot;Offscreen framebuffer with a color attachment texture.&quot;&quot;&quot;<br>
<br>
    @abstractmethod<br>
    def resize(self, size: Tuple[int, int]):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def color_texture(self) -&gt; TextureHandle:<br>
        &quot;&quot;&quot;TextureHandle for color attachment.&quot;&quot;&quot;<br>
        ...<br>
<br>
    @abstractmethod<br>
    def delete(self):<br>
        ...<br>
<br>
<br>
class GraphicsBackend(ABC):<br>
    &quot;&quot;&quot;Abstract graphics backend (OpenGL, Vulkan, etc.).&quot;&quot;&quot;<br>
<br>
    @abstractmethod<br>
    def ensure_ready(self):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_viewport(self, x: int, y: int, w: int, h: int):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def enable_scissor(self, x: int, y: int, w: int, h: int):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def disable_scissor(self):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def clear_color_depth(self, color):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_depth_test(self, enabled: bool):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_depth_mask(self, enabled: bool):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_depth_func(self, func: str):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_cull_face(self, enabled: bool):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_blend(self, enabled: bool):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_blend_func(self, src: str, dst: str):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def create_shader(self, vertex_source: str, fragment_source: str, geometry_source: str | None = None) -&gt; ShaderHandle:<br>
        ...<br>
<br>
    @abstractmethod<br>
    def create_mesh(self, mesh) -&gt; MeshHandle:<br>
        ...<br>
<br>
    @abstractmethod<br>
    def create_polyline(self, polyline) -&gt; PolylineHandle:<br>
        ...<br>
<br>
    @abstractmethod<br>
    def create_texture(self, image_data, size: Tuple[int, int], channels: int = 4, mipmap: bool = True, clamp: bool = False) -&gt; TextureHandle:<br>
        ...<br>
<br>
    @abstractmethod<br>
    def draw_ui_vertices(self, context_key: int, vertices):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def draw_ui_textured_quad(self, context_key: int):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_polygon_mode(self, mode: str):  # &quot;fill&quot; / &quot;line&quot;<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_cull_face_enabled(self, enabled: bool):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_depth_test_enabled(self, enabled: bool):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_depth_write_enabled(self, enabled: bool):<br>
        ...<br>
<br>
    def apply_render_state(self, state: RenderState):<br>
        &quot;&quot;&quot;<br>
        Применяет полное состояние рендера.<br>
        Все значения — абсолютные, без &quot;оставь как было&quot;.<br>
        &quot;&quot;&quot;<br>
        self.set_polygon_mode(state.polygon_mode)<br>
        self.set_cull_face(state.cull)<br>
        self.set_depth_test(state.depth_test)<br>
        self.set_depth_mask(state.depth_write)<br>
        self.set_blend(state.blend)<br>
        if state.blend:<br>
            self.set_blend_func(state.blend_src, state.blend_dst)<br>
<br>
    @abstractmethod<br>
    def read_pixel(self, framebuffer, x: int, y: int):<br>
        &quot;&quot;&quot;Вернуть (r,g,b,a) в [0,1] из указанного FBO.&quot;&quot;&quot;<br>
        ...<br>
<br>
    @abstractmethod<br>
    def create_framebuffer(self, size: Tuple[int, int]) -&gt; &quot;FramebufferHandle&quot;:<br>
        ...<br>
<br>
    @abstractmethod<br>
    def bind_framebuffer(self, framebuffer: &quot;FramebufferHandle | None&quot;):<br>
        &quot;&quot;&quot;<br>
        Bind custom framebuffer or default (if None).<br>
        &quot;&quot;&quot;<br>
        ...<br>
<br>
<br>
class BackendWindow(ABC):<br>
    &quot;&quot;&quot;Abstract window wrapper.&quot;&quot;&quot;<br>
<br>
    @abstractmethod<br>
    def bind_window_framebuffer(self):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def close(self):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def should_close(self) -&gt; bool:<br>
        ...<br>
<br>
    @abstractmethod<br>
    def make_current(self):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def swap_buffers(self):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def framebuffer_size(self) -&gt; Tuple[int, int]:<br>
        ...<br>
<br>
    @abstractmethod<br>
    def window_size(self) -&gt; Tuple[int, int]:<br>
        ...<br>
<br>
    @abstractmethod<br>
    def get_cursor_pos(self) -&gt; Tuple[float, float]:<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_should_close(self, flag: bool):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_user_pointer(self, ptr: Any):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_framebuffer_size_callback(self, callback: Callable):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_cursor_pos_callback(self, callback: Callable):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_scroll_callback(self, callback: Callable):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_mouse_button_callback(self, callback: Callable):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def set_key_callback(self, callback: Callable):<br>
        ...<br>
<br>
    def drives_render(self) -&gt; bool:<br>
        &quot;&quot;&quot;<br>
        Возвращает True, если рендер вызывается бекэндом самостоятельно (например, Qt виджет),<br>
        и False, если движок сам вызывает render() каждый кадр (например, GLFW).<br>
        &quot;&quot;&quot;<br>
        return False<br>
<br>
    <br>
    @abstractmethod<br>
    def request_update(self):<br>
        ...<br>
<br>
<br>
class WindowBackend(ABC):<br>
    &quot;&quot;&quot;Abstract window backend (GLFW, SDL, etc.).&quot;&quot;&quot;<br>
<br>
    @abstractmethod<br>
    def create_window(self, width: int, height: int, title: str, share: Optional[Any] = None) -&gt; BackendWindow:<br>
        ...<br>
<br>
    @abstractmethod<br>
    def poll_events(self):<br>
        ...<br>
<br>
    @abstractmethod<br>
    def terminate(self):<br>
        ...<br>
<br>
<!-- END SCAT CODE -->
</body>
</html>
