<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/visualization/backends/nop_graphics.py</title>
</head>
<body>
<pre><code>
# termin/visualization/backends/nop.py
from __future__ import annotations

from typing import Any, Optional, Tuple

from .base import (
    Action,
    BackendWindow,
    FramebufferHandle,
    GraphicsBackend,
    Key,
    MeshHandle,
    MouseButton,
    PolylineHandle,
    ShaderHandle,
    TextureHandle,
    WindowBackend,
)


# --- NOP-обёртки для GPU-ресурсов ---------------------------------------


class NOPShaderHandle(ShaderHandle):
    &quot;&quot;&quot;Шейдер, который &quot;существует&quot;, но ничего не делает.&quot;&quot;&quot;

    def use(self):
        pass

    def stop(self):
        pass

    def delete(self):
        pass

    def set_uniform_matrix4(self, name: str, matrix):
        pass

    def set_uniform_vec2(self, name: str, vector):
        pass

    def set_uniform_vec3(self, name: str, vector):
        pass

    def set_uniform_vec4(self, name: str, vector):
        pass

    def set_uniform_float(self, name: str, value: float):
        pass

    def set_uniform_int(self, name: str, value: int):
        pass


class NOPMeshHandle(MeshHandle):
    &quot;&quot;&quot;Меш-хэндл (указатель на геометрию), который ничего не рисует.&quot;&quot;&quot;

    def draw(self):
        pass

    def delete(self):
        pass


class NOPPolylineHandle(PolylineHandle):
    &quot;&quot;&quot;Полилиния, которая тоже ничего не рисует.&quot;&quot;&quot;

    def draw(self):
        pass

    def delete(self):
        pass


class NOPTextureHandle(TextureHandle):
    &quot;&quot;&quot;Текстура-заглушка.&quot;&quot;&quot;

    def bind(self, unit: int = 0):
        pass

    def delete(self):
        pass


class NOPFramebufferHandle(FramebufferHandle):
    &quot;&quot;&quot;Фреймбуфер (offscreen буфер), который не привязан к реальному GPU.&quot;&quot;&quot;

    def __init__(self, size: Tuple[int, int]):
        self._size = size
        # Отдаём какую-то текстуру, чтобы postprocess не падал
        self._color_tex = NOPTextureHandle()

    def resize(self, size: Tuple[int, int]):
        self._size = size

    def color_texture(self) -&gt; TextureHandle:
        return self._color_tex

    def delete(self):
        pass


# --- Графический бэкенд без реального рендера ---------------------------


class NOPGraphicsBackend(GraphicsBackend):
    &quot;&quot;&quot;
    GraphicsBackend, который удовлетворяет интерфейсу, но:
    - ничего не рисует;
    - не инициализирует OpenGL (или любой другой API);
    - годится для юнит-тестов и проверки примеров.
    &quot;&quot;&quot;

    def __init__(self):
        self._viewport: Tuple[int, int, int, int] = (0, 0, 0, 0)
        # Можно хранить последнее состояние рендера, если захочешь дебажить
        self._state = {}

    def ensure_ready(self):
        # Никакой инициализации не требуется
        pass

    def set_viewport(self, x: int, y: int, w: int, h: int):
        self._viewport = (x, y, w, h)

    def enable_scissor(self, x: int, y: int, w: int, h: int):
        pass

    def disable_scissor(self):
        pass

    def clear_color_depth(self, color):
        # Никакого чистки буферов — просто заглушка
        pass

    def set_depth_test(self, enabled: bool):
        self._state[&quot;depth_test&quot;] = enabled

    def set_depth_mask(self, enabled: bool):
        self._state[&quot;depth_mask&quot;] = enabled

    def set_depth_func(self, func: str):
        self._state[&quot;depth_func&quot;] = func

    def set_cull_face(self, enabled: bool):
        self._state[&quot;cull_face&quot;] = enabled

    def set_blend(self, enabled: bool):
        self._state[&quot;blend&quot;] = enabled

    def set_blend_func(self, src: str, dst: str):
        self._state[&quot;blend_func&quot;] = (src, dst)

    def create_shader(
        self,
        vertex_source: str,
        fragment_source: str,
        geometry_source: str | None = None,
    ) -&gt; ShaderHandle:
        # Можно сохранять исходники, если нужно для отладки
        return NOPShaderHandle()

    def create_mesh(self, mesh) -&gt; MeshHandle:
        return NOPMeshHandle()

    def create_polyline(self, polyline) -&gt; PolylineHandle:
        return NOPPolylineHandle()

    def create_texture(
        self,
        image_data,
        size: Tuple[int, int],
        channels: int = 4,
        mipmap: bool = True,
        clamp: bool = False,
    ) -&gt; TextureHandle:
        return NOPTextureHandle()

    def draw_ui_vertices(self, context_key: int, vertices):
        # Ничего не рисуем
        pass

    def draw_ui_textured_quad(self, context_key: int, vertices=None):
        &quot;&quot;&quot;
        Обрати внимание: здесь параметр vertices сделан опциональным.
        Это чтобы пережить оба варианта вызова:
        - draw_ui_textured_quad(context_key)
        - draw_ui_textured_quad(context_key, vertices)
        &quot;&quot;&quot;
        pass

    def set_polygon_mode(self, mode: str):
        self._state[&quot;polygon_mode&quot;] = mode

    def set_cull_face_enabled(self, enabled: bool):
        self._state[&quot;cull_face&quot;] = enabled

    def set_depth_test_enabled(self, enabled: bool):
        self._state[&quot;depth_test&quot;] = enabled

    def set_depth_write_enabled(self, enabled: bool):
        self._state[&quot;depth_mask&quot;] = enabled

    def create_framebuffer(self, size: Tuple[int, int]) -&gt; FramebufferHandle:
        return NOPFramebufferHandle(size)

    def bind_framebuffer(self, framebuffer: FramebufferHandle | None):
        # Можно сохранить ссылку, если нужно для отладки
        self._state[&quot;bound_fbo&quot;] = framebuffer

    def read_pixel(self, x: int, y: int) -&gt; Any:
        # Возвращаем пустые данные
        return None
</code></pre>
</body>
</html>
