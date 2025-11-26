<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/backends/nop_graphics.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
# termin/visualization/backends/nop.py<br>
from __future__ import annotations<br>
<br>
from typing import Any, Optional, Tuple<br>
<br>
from .base import (<br>
    Action,<br>
    BackendWindow,<br>
    FramebufferHandle,<br>
    GraphicsBackend,<br>
    Key,<br>
    MeshHandle,<br>
    MouseButton,<br>
    PolylineHandle,<br>
    ShaderHandle,<br>
    TextureHandle,<br>
    WindowBackend,<br>
)<br>
<br>
<br>
# --- NOP-обёртки для GPU-ресурсов ---------------------------------------<br>
<br>
<br>
class NOPShaderHandle(ShaderHandle):<br>
    &quot;&quot;&quot;Шейдер, который &quot;существует&quot;, но ничего не делает.&quot;&quot;&quot;<br>
<br>
    def use(self):<br>
        pass<br>
<br>
    def stop(self):<br>
        pass<br>
<br>
    def delete(self):<br>
        pass<br>
<br>
    def set_uniform_matrix4(self, name: str, matrix):<br>
        pass<br>
<br>
    def set_uniform_vec2(self, name: str, vector):<br>
        pass<br>
<br>
    def set_uniform_vec3(self, name: str, vector):<br>
        pass<br>
<br>
    def set_uniform_vec4(self, name: str, vector):<br>
        pass<br>
<br>
    def set_uniform_float(self, name: str, value: float):<br>
        pass<br>
<br>
    def set_uniform_int(self, name: str, value: int):<br>
        pass<br>
<br>
<br>
class NOPMeshHandle(MeshHandle):<br>
    &quot;&quot;&quot;Меш-хэндл (указатель на геометрию), который ничего не рисует.&quot;&quot;&quot;<br>
<br>
    def draw(self):<br>
        pass<br>
<br>
    def delete(self):<br>
        pass<br>
<br>
<br>
class NOPPolylineHandle(PolylineHandle):<br>
    &quot;&quot;&quot;Полилиния, которая тоже ничего не рисует.&quot;&quot;&quot;<br>
<br>
    def draw(self):<br>
        pass<br>
<br>
    def delete(self):<br>
        pass<br>
<br>
<br>
class NOPTextureHandle(TextureHandle):<br>
    &quot;&quot;&quot;Текстура-заглушка.&quot;&quot;&quot;<br>
<br>
    def bind(self, unit: int = 0):<br>
        pass<br>
<br>
    def delete(self):<br>
        pass<br>
<br>
<br>
class NOPFramebufferHandle(FramebufferHandle):<br>
    &quot;&quot;&quot;Фреймбуфер (offscreen буфер), который не привязан к реальному GPU.&quot;&quot;&quot;<br>
<br>
    def __init__(self, size: Tuple[int, int]):<br>
        self._size = size<br>
        # Отдаём какую-то текстуру, чтобы postprocess не падал<br>
        self._color_tex = NOPTextureHandle()<br>
<br>
    def resize(self, size: Tuple[int, int]):<br>
        self._size = size<br>
<br>
    def color_texture(self) -&gt; TextureHandle:<br>
        return self._color_tex<br>
<br>
    def delete(self):<br>
        pass<br>
<br>
<br>
# --- Графический бэкенд без реального рендера ---------------------------<br>
<br>
<br>
class NOPGraphicsBackend(GraphicsBackend):<br>
    &quot;&quot;&quot;<br>
    GraphicsBackend, который удовлетворяет интерфейсу, но:<br>
    - ничего не рисует;<br>
    - не инициализирует OpenGL (или любой другой API);<br>
    - годится для юнит-тестов и проверки примеров.<br>
    &quot;&quot;&quot;<br>
<br>
    def __init__(self):<br>
        self._viewport: Tuple[int, int, int, int] = (0, 0, 0, 0)<br>
        # Можно хранить последнее состояние рендера, если захочешь дебажить<br>
        self._state = {}<br>
<br>
    def ensure_ready(self):<br>
        # Никакой инициализации не требуется<br>
        pass<br>
<br>
    def set_viewport(self, x: int, y: int, w: int, h: int):<br>
        self._viewport = (x, y, w, h)<br>
<br>
    def enable_scissor(self, x: int, y: int, w: int, h: int):<br>
        pass<br>
<br>
    def disable_scissor(self):<br>
        pass<br>
<br>
    def clear_color_depth(self, color):<br>
        # Никакого чистки буферов — просто заглушка<br>
        pass<br>
<br>
    def set_depth_test(self, enabled: bool):<br>
        self._state[&quot;depth_test&quot;] = enabled<br>
<br>
    def set_depth_mask(self, enabled: bool):<br>
        self._state[&quot;depth_mask&quot;] = enabled<br>
<br>
    def set_depth_func(self, func: str):<br>
        self._state[&quot;depth_func&quot;] = func<br>
<br>
    def set_cull_face(self, enabled: bool):<br>
        self._state[&quot;cull_face&quot;] = enabled<br>
<br>
    def set_blend(self, enabled: bool):<br>
        self._state[&quot;blend&quot;] = enabled<br>
<br>
    def set_blend_func(self, src: str, dst: str):<br>
        self._state[&quot;blend_func&quot;] = (src, dst)<br>
<br>
    def create_shader(<br>
        self,<br>
        vertex_source: str,<br>
        fragment_source: str,<br>
        geometry_source: str | None = None,<br>
    ) -&gt; ShaderHandle:<br>
        # Можно сохранять исходники, если нужно для отладки<br>
        return NOPShaderHandle()<br>
<br>
    def create_mesh(self, mesh) -&gt; MeshHandle:<br>
        return NOPMeshHandle()<br>
<br>
    def create_polyline(self, polyline) -&gt; PolylineHandle:<br>
        return NOPPolylineHandle()<br>
<br>
    def create_texture(<br>
        self,<br>
        image_data,<br>
        size: Tuple[int, int],<br>
        channels: int = 4,<br>
        mipmap: bool = True,<br>
        clamp: bool = False,<br>
    ) -&gt; TextureHandle:<br>
        return NOPTextureHandle()<br>
<br>
    def draw_ui_vertices(self, context_key: int, vertices):<br>
        # Ничего не рисуем<br>
        pass<br>
<br>
    def draw_ui_textured_quad(self, context_key: int, vertices=None):<br>
        &quot;&quot;&quot;<br>
        Обрати внимание: здесь параметр vertices сделан опциональным.<br>
        Это чтобы пережить оба варианта вызова:<br>
        - draw_ui_textured_quad(context_key)<br>
        - draw_ui_textured_quad(context_key, vertices)<br>
        &quot;&quot;&quot;<br>
        pass<br>
<br>
    def set_polygon_mode(self, mode: str):<br>
        self._state[&quot;polygon_mode&quot;] = mode<br>
<br>
    def set_cull_face_enabled(self, enabled: bool):<br>
        self._state[&quot;cull_face&quot;] = enabled<br>
<br>
    def set_depth_test_enabled(self, enabled: bool):<br>
        self._state[&quot;depth_test&quot;] = enabled<br>
<br>
    def set_depth_write_enabled(self, enabled: bool):<br>
        self._state[&quot;depth_mask&quot;] = enabled<br>
<br>
    def create_framebuffer(self, size: Tuple[int, int]) -&gt; FramebufferHandle:<br>
        return NOPFramebufferHandle(size)<br>
<br>
    def bind_framebuffer(self, framebuffer: FramebufferHandle | None):<br>
        # Можно сохранить ссылку, если нужно для отладки<br>
        self._state[&quot;bound_fbo&quot;] = framebuffer<br>
<br>
    def read_pixel(self, x: int, y: int) -&gt; Any:<br>
        # Возвращаем пустые данные<br>
        return None<br>
<!-- END SCAT CODE -->
</body>
</html>
