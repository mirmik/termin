"""Backend interfaces decoupling rendering/window code from specific libraries."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import IntEnum
from typing import Any, Callable, Optional, Tuple


class Action(IntEnum):
    RELEASE = 0
    PRESS = 1
    REPEAT = 2


class MouseButton(IntEnum):
    LEFT = 0
    RIGHT = 1
    MIDDLE = 2


class Key(IntEnum):
    UNKNOWN = -1
    SPACE = 32
    ESCAPE = 256


class ShaderHandle(ABC):
    """Backend-specific shader program."""

    @abstractmethod
    def use(self):
        ...

    @abstractmethod
    def stop(self):
        ...

    @abstractmethod
    def delete(self):
        ...

    @abstractmethod
    def set_uniform_matrix4(self, name: str, matrix):
        ...

    @abstractmethod
    def set_uniform_vec3(self, name: str, vector):
        ...

    @abstractmethod
    def set_uniform_vec4(self, name: str, vector):
        ...

    @abstractmethod
    def set_uniform_float(self, name: str, value: float):
        ...

    @abstractmethod
    def set_uniform_int(self, name: str, value: int):
        ...


class MeshHandle(ABC):
    """Backend mesh buffers ready for drawing."""

    @abstractmethod
    def draw(self):
        ...

    @abstractmethod
    def delete(self):
        ...


class PolylineHandle(ABC):
    """Backend polyline buffers."""

    @abstractmethod
    def draw(self):
        ...

    @abstractmethod
    def delete(self):
        ...


class TextureHandle(ABC):
    """Backend texture object."""

    @abstractmethod
    def bind(self, unit: int = 0):
        ...

    @abstractmethod
    def delete(self):
        ...

class FramebufferHandle(ABC):
    """Offscreen framebuffer with a color attachment texture."""

    @abstractmethod
    def resize(self, size: Tuple[int, int]):
        ...

    @abstractmethod
    def color_texture(self) -> TextureHandle:
        """TextureHandle for color attachment."""
        ...

    @abstractmethod
    def delete(self):
        ...


class GraphicsBackend(ABC):
    """Abstract graphics backend (OpenGL, Vulkan, etc.)."""

    @abstractmethod
    def ensure_ready(self):
        ...

    @abstractmethod
    def set_viewport(self, x: int, y: int, w: int, h: int):
        ...

    @abstractmethod
    def enable_scissor(self, x: int, y: int, w: int, h: int):
        ...

    @abstractmethod
    def disable_scissor(self):
        ...

    @abstractmethod
    def clear_color_depth(self, color):
        ...

    @abstractmethod
    def set_depth_test(self, enabled: bool):
        ...

    @abstractmethod
    def set_depth_mask(self, enabled: bool):
        ...

    @abstractmethod
    def set_depth_func(self, func: str):
        ...

    @abstractmethod
    def set_cull_face(self, enabled: bool):
        ...

    @abstractmethod
    def set_blend(self, enabled: bool):
        ...

    @abstractmethod
    def set_blend_func(self, src: str, dst: str):
        ...

    @abstractmethod
    def create_shader(self, vertex_source: str, fragment_source: str, geometry_source: str | None = None) -> ShaderHandle:
        ...

    @abstractmethod
    def create_mesh(self, mesh) -> MeshHandle:
        ...

    @abstractmethod
    def create_polyline(self, polyline) -> PolylineHandle:
        ...

    @abstractmethod
    def create_texture(self, image_data, size: Tuple[int, int], channels: int = 4, mipmap: bool = True, clamp: bool = False) -> TextureHandle:
        ...

    @abstractmethod
    def draw_ui_vertices(self, context_key: int, vertices):
        ...

    @abstractmethod
    def draw_ui_textured_quad(self, context_key: int):
        ...

    @abstractmethod
    def set_polygon_mode(self, mode: str):  # "fill" / "line"
        ...

    @abstractmethod
    def set_cull_face_enabled(self, enabled: bool):
        ...

    @abstractmethod
    def set_depth_test_enabled(self, enabled: bool):
        ...

    @abstractmethod
    def set_depth_write_enabled(self, enabled: bool):
        ...

    def apply_render_state(self, state: RenderState):
        """
        Применяет полное состояние рендера.
        Все значения — абсолютные, без "оставь как было".
        """
        self.set_polygon_mode(state.polygon_mode)
        self.set_cull_face(state.cull)
        self.set_depth_test(state.depth_test)
        self.set_depth_mask(state.depth_write)
        self.set_blend(state.blend)
        if state.blend:
            self.set_blend_func(state.blend_src, state.blend_dst)

    @abstractmethod
    def read_pixel(self, framebuffer, x: int, y: int):
        """Вернуть (r,g,b,a) в [0,1] из указанного FBO."""
        ...

    @abstractmethod
    def create_framebuffer(self, size: Tuple[int, int]) -> "FramebufferHandle":
        ...

    @abstractmethod
    def bind_framebuffer(self, framebuffer: "FramebufferHandle | None"):
        """
        Bind custom framebuffer or default (if None).
        """
        ...


class BackendWindow(ABC):
    """Abstract window wrapper."""

    @abstractmethod
    def bind_window_framebuffer(self):
        ...

    @abstractmethod
    def close(self):
        ...

    @abstractmethod
    def should_close(self) -> bool:
        ...

    @abstractmethod
    def make_current(self):
        ...

    @abstractmethod
    def swap_buffers(self):
        ...

    @abstractmethod
    def framebuffer_size(self) -> Tuple[int, int]:
        ...

    @abstractmethod
    def window_size(self) -> Tuple[int, int]:
        ...

    @abstractmethod
    def get_cursor_pos(self) -> Tuple[float, float]:
        ...

    @abstractmethod
    def set_should_close(self, flag: bool):
        ...

    @abstractmethod
    def set_user_pointer(self, ptr: Any):
        ...

    @abstractmethod
    def set_framebuffer_size_callback(self, callback: Callable):
        ...

    @abstractmethod
    def set_cursor_pos_callback(self, callback: Callable):
        ...

    @abstractmethod
    def set_scroll_callback(self, callback: Callable):
        ...

    @abstractmethod
    def set_mouse_button_callback(self, callback: Callable):
        ...

    @abstractmethod
    def set_key_callback(self, callback: Callable):
        ...

    def drives_render(self) -> bool:
        """
        Возвращает True, если рендер вызывается бекэндом самостоятельно (например, Qt виджет),
        и False, если движок сам вызывает render() каждый кадр (например, GLFW).
        """
        return False

    
    @abstractmethod
    def request_update(self):
        ...


class WindowBackend(ABC):
    """Abstract window backend (GLFW, SDL, etc.)."""

    @abstractmethod
    def create_window(self, width: int, height: int, title: str, share: Optional[Any] = None) -> BackendWindow:
        ...

    @abstractmethod
    def poll_events(self):
        ...

    @abstractmethod
    def terminate(self):
        ...

