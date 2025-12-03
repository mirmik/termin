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
    """Шейдер, который "существует", но ничего не делает."""

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
    """Меш-хэндл (указатель на геометрию), который ничего не рисует."""

    def draw(self):
        pass

    def delete(self):
        pass


class NOPPolylineHandle(PolylineHandle):
    """Полилиния, которая тоже ничего не рисует."""

    def draw(self):
        pass

    def delete(self):
        pass


class NOPTextureHandle(TextureHandle):
    """Текстура-заглушка."""

    def bind(self, unit: int = 0):
        pass

    def delete(self):
        pass


class NOPFramebufferHandle(FramebufferHandle):
    """Фреймбуфер (offscreen буфер), который не привязан к реальному GPU."""

    def __init__(self, size: Tuple[int, int]):
        self._size = size
        # Отдаём какую-то текстуру, чтобы postprocess не падал
        self._color_tex = NOPTextureHandle()

    def resize(self, size: Tuple[int, int]):
        self._size = size

    def color_texture(self) -> TextureHandle:
        return self._color_tex

    def delete(self):
        pass


# --- Графический бэкенд без реального рендера ---------------------------


class NOPGraphicsBackend(GraphicsBackend):
    """
    GraphicsBackend, который удовлетворяет интерфейсу, но:
    - ничего не рисует;
    - не инициализирует OpenGL (или любой другой API);
    - годится для юнит-тестов и проверки примеров.
    """

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

    def set_color_mask(self, r: bool, g: bool, b: bool, a: bool):
        self._state["color_mask"] = (r, g, b, a)

    def set_depth_test(self, enabled: bool):
        self._state["depth_test"] = enabled

    def set_depth_mask(self, enabled: bool):
        self._state["depth_mask"] = enabled

    def set_depth_func(self, func: str):
        self._state["depth_func"] = func

    def set_cull_face(self, enabled: bool):
        self._state["cull_face"] = enabled

    def set_blend(self, enabled: bool):
        self._state["blend"] = enabled

    def set_blend_func(self, src: str, dst: str):
        self._state["blend_func"] = (src, dst)

    def create_shader(
        self,
        vertex_source: str,
        fragment_source: str,
        geometry_source: str | None = None,
    ) -> ShaderHandle:
        # Можно сохранять исходники, если нужно для отладки
        return NOPShaderHandle()

    def create_mesh(self, mesh) -> MeshHandle:
        return NOPMeshHandle()

    def create_polyline(self, polyline) -> PolylineHandle:
        return NOPPolylineHandle()

    def create_texture(
        self,
        image_data,
        size: Tuple[int, int],
        channels: int = 4,
        mipmap: bool = True,
        clamp: bool = False,
    ) -> TextureHandle:
        return NOPTextureHandle()

    def draw_ui_vertices(self, context_key: int, vertices):
        # Ничего не рисуем
        pass

    def draw_ui_textured_quad(self, context_key: int, vertices=None):
        """
        Обрати внимание: здесь параметр vertices сделан опциональным.
        Это чтобы пережить оба варианта вызова:
        - draw_ui_textured_quad(context_key)
        - draw_ui_textured_quad(context_key, vertices)
        """
        pass

    def set_polygon_mode(self, mode: str):
        self._state["polygon_mode"] = mode

    def set_cull_face_enabled(self, enabled: bool):
        self._state["cull_face"] = enabled

    def set_depth_test_enabled(self, enabled: bool):
        self._state["depth_test"] = enabled

    def set_depth_write_enabled(self, enabled: bool):
        self._state["depth_mask"] = enabled

    def create_framebuffer(self, size: Tuple[int, int]) -> FramebufferHandle:
        return NOPFramebufferHandle(size)

    def bind_framebuffer(self, framebuffer: FramebufferHandle | None):
        # Можно сохранить ссылку, если нужно для отладки
        self._state["bound_fbo"] = framebuffer

    def read_pixel(self, framebuffer, x: int, y: int) -> Any:
        # Возвращаем пустые данные
        return None

    def read_depth_buffer(self, framebuffer):
        return None
