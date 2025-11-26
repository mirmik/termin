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
&#9;Action,<br>
&#9;BackendWindow,<br>
&#9;FramebufferHandle,<br>
&#9;GraphicsBackend,<br>
&#9;Key,<br>
&#9;MeshHandle,<br>
&#9;MouseButton,<br>
&#9;PolylineHandle,<br>
&#9;ShaderHandle,<br>
&#9;TextureHandle,<br>
&#9;WindowBackend,<br>
)<br>
<br>
<br>
# --- NOP-обёртки для GPU-ресурсов ---------------------------------------<br>
<br>
<br>
class NOPShaderHandle(ShaderHandle):<br>
&#9;&quot;&quot;&quot;Шейдер, который &quot;существует&quot;, но ничего не делает.&quot;&quot;&quot;<br>
<br>
&#9;def use(self):<br>
&#9;&#9;pass<br>
<br>
&#9;def stop(self):<br>
&#9;&#9;pass<br>
<br>
&#9;def delete(self):<br>
&#9;&#9;pass<br>
<br>
&#9;def set_uniform_matrix4(self, name: str, matrix):<br>
&#9;&#9;pass<br>
<br>
&#9;def set_uniform_vec2(self, name: str, vector):<br>
&#9;&#9;pass<br>
<br>
&#9;def set_uniform_vec3(self, name: str, vector):<br>
&#9;&#9;pass<br>
<br>
&#9;def set_uniform_vec4(self, name: str, vector):<br>
&#9;&#9;pass<br>
<br>
&#9;def set_uniform_float(self, name: str, value: float):<br>
&#9;&#9;pass<br>
<br>
&#9;def set_uniform_int(self, name: str, value: int):<br>
&#9;&#9;pass<br>
<br>
<br>
class NOPMeshHandle(MeshHandle):<br>
&#9;&quot;&quot;&quot;Меш-хэндл (указатель на геометрию), который ничего не рисует.&quot;&quot;&quot;<br>
<br>
&#9;def draw(self):<br>
&#9;&#9;pass<br>
<br>
&#9;def delete(self):<br>
&#9;&#9;pass<br>
<br>
<br>
class NOPPolylineHandle(PolylineHandle):<br>
&#9;&quot;&quot;&quot;Полилиния, которая тоже ничего не рисует.&quot;&quot;&quot;<br>
<br>
&#9;def draw(self):<br>
&#9;&#9;pass<br>
<br>
&#9;def delete(self):<br>
&#9;&#9;pass<br>
<br>
<br>
class NOPTextureHandle(TextureHandle):<br>
&#9;&quot;&quot;&quot;Текстура-заглушка.&quot;&quot;&quot;<br>
<br>
&#9;def bind(self, unit: int = 0):<br>
&#9;&#9;pass<br>
<br>
&#9;def delete(self):<br>
&#9;&#9;pass<br>
<br>
<br>
class NOPFramebufferHandle(FramebufferHandle):<br>
&#9;&quot;&quot;&quot;Фреймбуфер (offscreen буфер), который не привязан к реальному GPU.&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self, size: Tuple[int, int]):<br>
&#9;&#9;self._size = size<br>
&#9;&#9;# Отдаём какую-то текстуру, чтобы postprocess не падал<br>
&#9;&#9;self._color_tex = NOPTextureHandle()<br>
<br>
&#9;def resize(self, size: Tuple[int, int]):<br>
&#9;&#9;self._size = size<br>
<br>
&#9;def color_texture(self) -&gt; TextureHandle:<br>
&#9;&#9;return self._color_tex<br>
<br>
&#9;def delete(self):<br>
&#9;&#9;pass<br>
<br>
<br>
# --- Графический бэкенд без реального рендера ---------------------------<br>
<br>
<br>
class NOPGraphicsBackend(GraphicsBackend):<br>
&#9;&quot;&quot;&quot;<br>
&#9;GraphicsBackend, который удовлетворяет интерфейсу, но:<br>
&#9;- ничего не рисует;<br>
&#9;- не инициализирует OpenGL (или любой другой API);<br>
&#9;- годится для юнит-тестов и проверки примеров.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;def __init__(self):<br>
&#9;&#9;self._viewport: Tuple[int, int, int, int] = (0, 0, 0, 0)<br>
&#9;&#9;# Можно хранить последнее состояние рендера, если захочешь дебажить<br>
&#9;&#9;self._state = {}<br>
<br>
&#9;def ensure_ready(self):<br>
&#9;&#9;# Никакой инициализации не требуется<br>
&#9;&#9;pass<br>
<br>
&#9;def set_viewport(self, x: int, y: int, w: int, h: int):<br>
&#9;&#9;self._viewport = (x, y, w, h)<br>
<br>
&#9;def enable_scissor(self, x: int, y: int, w: int, h: int):<br>
&#9;&#9;pass<br>
<br>
&#9;def disable_scissor(self):<br>
&#9;&#9;pass<br>
<br>
&#9;def clear_color_depth(self, color):<br>
&#9;&#9;# Никакого чистки буферов — просто заглушка<br>
&#9;&#9;pass<br>
<br>
&#9;def set_depth_test(self, enabled: bool):<br>
&#9;&#9;self._state[&quot;depth_test&quot;] = enabled<br>
<br>
&#9;def set_depth_mask(self, enabled: bool):<br>
&#9;&#9;self._state[&quot;depth_mask&quot;] = enabled<br>
<br>
&#9;def set_depth_func(self, func: str):<br>
&#9;&#9;self._state[&quot;depth_func&quot;] = func<br>
<br>
&#9;def set_cull_face(self, enabled: bool):<br>
&#9;&#9;self._state[&quot;cull_face&quot;] = enabled<br>
<br>
&#9;def set_blend(self, enabled: bool):<br>
&#9;&#9;self._state[&quot;blend&quot;] = enabled<br>
<br>
&#9;def set_blend_func(self, src: str, dst: str):<br>
&#9;&#9;self._state[&quot;blend_func&quot;] = (src, dst)<br>
<br>
&#9;def create_shader(<br>
&#9;&#9;self,<br>
&#9;&#9;vertex_source: str,<br>
&#9;&#9;fragment_source: str,<br>
&#9;&#9;geometry_source: str | None = None,<br>
&#9;) -&gt; ShaderHandle:<br>
&#9;&#9;# Можно сохранять исходники, если нужно для отладки<br>
&#9;&#9;return NOPShaderHandle()<br>
<br>
&#9;def create_mesh(self, mesh) -&gt; MeshHandle:<br>
&#9;&#9;return NOPMeshHandle()<br>
<br>
&#9;def create_polyline(self, polyline) -&gt; PolylineHandle:<br>
&#9;&#9;return NOPPolylineHandle()<br>
<br>
&#9;def create_texture(<br>
&#9;&#9;self,<br>
&#9;&#9;image_data,<br>
&#9;&#9;size: Tuple[int, int],<br>
&#9;&#9;channels: int = 4,<br>
&#9;&#9;mipmap: bool = True,<br>
&#9;&#9;clamp: bool = False,<br>
&#9;) -&gt; TextureHandle:<br>
&#9;&#9;return NOPTextureHandle()<br>
<br>
&#9;def draw_ui_vertices(self, context_key: int, vertices):<br>
&#9;&#9;# Ничего не рисуем<br>
&#9;&#9;pass<br>
<br>
&#9;def draw_ui_textured_quad(self, context_key: int, vertices=None):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Обрати внимание: здесь параметр vertices сделан опциональным.<br>
&#9;&#9;Это чтобы пережить оба варианта вызова:<br>
&#9;&#9;- draw_ui_textured_quad(context_key)<br>
&#9;&#9;- draw_ui_textured_quad(context_key, vertices)<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;pass<br>
<br>
&#9;def set_polygon_mode(self, mode: str):<br>
&#9;&#9;self._state[&quot;polygon_mode&quot;] = mode<br>
<br>
&#9;def set_cull_face_enabled(self, enabled: bool):<br>
&#9;&#9;self._state[&quot;cull_face&quot;] = enabled<br>
<br>
&#9;def set_depth_test_enabled(self, enabled: bool):<br>
&#9;&#9;self._state[&quot;depth_test&quot;] = enabled<br>
<br>
&#9;def set_depth_write_enabled(self, enabled: bool):<br>
&#9;&#9;self._state[&quot;depth_mask&quot;] = enabled<br>
<br>
&#9;def create_framebuffer(self, size: Tuple[int, int]) -&gt; FramebufferHandle:<br>
&#9;&#9;return NOPFramebufferHandle(size)<br>
<br>
&#9;def bind_framebuffer(self, framebuffer: FramebufferHandle | None):<br>
&#9;&#9;# Можно сохранить ссылку, если нужно для отладки<br>
&#9;&#9;self._state[&quot;bound_fbo&quot;] = framebuffer<br>
<br>
&#9;def read_pixel(self, x: int, y: int) -&gt; Any:<br>
&#9;&#9;# Возвращаем пустые данные<br>
&#9;&#9;return None<br>
<!-- END SCAT CODE -->
</body>
</html>
