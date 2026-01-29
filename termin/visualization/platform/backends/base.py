"""Backend interfaces decoupling rendering/window code from specific libraries."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import IntEnum
from typing import Any, Callable, Optional, Tuple

# Re-export C++ enums for Action, MouseButton, Mods
from termin.entity._entity_native import Action, MouseButton, Mods


class Key(IntEnum):
    UNKNOWN = -1
    TAB = 9
    ENTER = 13
    SPACE = 32

    # Numbers (ASCII)
    KEY_0 = 48
    KEY_1 = 49
    KEY_2 = 50
    KEY_3 = 51
    KEY_4 = 52
    KEY_5 = 53
    KEY_6 = 54
    KEY_7 = 55
    KEY_8 = 56
    KEY_9 = 57

    # Letters (ASCII uppercase)
    A = 65
    B = 66
    C = 67
    D = 68
    E = 69
    F = 70
    G = 71
    H = 72
    I = 73
    J = 74
    K = 75
    L = 76
    M = 77
    N = 78
    O = 79
    P = 80
    Q = 81
    R = 82
    S = 83
    T = 84
    U = 85
    V = 86
    W = 87
    X = 88
    Y = 89
    Z = 90

    # Special keys (GLFW-compatible values)
    ESCAPE = 256
    BACKSPACE = 259
    DELETE = 261
    RIGHT = 262
    LEFT = 263
    DOWN = 264
    UP = 265

    # Function keys
    F1 = 290
    F2 = 291
    F3 = 292
    F4 = 293
    F5 = 294
    F6 = 295
    F7 = 296
    F8 = 297
    F9 = 298
    F10 = 299
    F11 = 300
    F12 = 301


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

    @abstractmethod
    def set_uniform_matrix4_array(self, name: str, matrices, count: int):
        """
        Set an array of 4x4 matrices as uniform.

        Args:
            name: Uniform name (e.g., "u_bone_matrices")
            matrices: Array of shape (count, 4, 4) or flattened
            count: Number of matrices
        """
        ...


class MeshHandle(ABC):
    """Backend mesh buffers ready for drawing."""

    @abstractmethod
    def draw(self):
        ...

    @abstractmethod
    def delete(self):
        ...


class GPUTextureHandle(ABC):
    """Backend GPU texture object."""

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
    def color_texture(self) -> GPUTextureHandle:
        """GPUTextureHandle for color attachment."""
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
    def set_color_mask(self, r: bool, g: bool, b: bool, a: bool) -> None:
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
    def reset_state(self) -> None:
        """
        Сбрасывает состояние в дефолтное для opaque color pass.

        Устанавливает:
        - Depth test: enabled, func=LESS, mask=TRUE
        - Blend: disabled
        - Cull face: enabled, back, CCW
        - Polygon mode: fill
        - Color mask: all true
        - Stencil: disabled
        - Scissor: disabled
        """
        ...

    @abstractmethod
    def create_shader(self, vertex_source: str, fragment_source: str, geometry_source: str | None = None) -> ShaderHandle:
        ...

    @abstractmethod
    def create_mesh(self, mesh) -> MeshHandle:
        ...

    @abstractmethod
    def create_texture(self, image_data, size: Tuple[int, int], channels: int = 4, mipmap: bool = True, clamp: bool = False) -> GPUTextureHandle:
        ...

    @abstractmethod
    def draw_ui_vertices(self, vertices):
        ...

    @abstractmethod
    def draw_ui_textured_quad(self):
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
    def read_depth_buffer(self, framebuffer):
        """
        Вернуть depth-буфер из указанного FBO как numpy-массив float32 формы (h, w)
        или None, если чтение невозможно.
        """
        ...

    @abstractmethod
    def read_depth_pixel(self, framebuffer, x: int, y: int) -> float | None:
        """
        Вернуть значение глубины в указанной точке FBO.
        Координаты x, y в пикселях FBO (origin снизу-слева).
        Возвращает depth в [0, 1] или None при ошибке.
        """
        ...

    @abstractmethod
    def flush(self) -> None:
        """
        Force submit commands to GPU (non-blocking).
        Equivalent to glFlush().
        """
        ...

    @abstractmethod
    def finish(self) -> None:
        """
        Wait for GPU to complete all commands (blocking).
        Equivalent to glFinish().
        """
        ...

    @abstractmethod
    def create_framebuffer(self, size: Tuple[int, int], samples: int = 1) -> "FramebufferHandle":
        """
        Создаёт framebuffer с цветовым и depth attachment.

        Параметры:
            size: Размер (width, height).
            samples: Количество MSAA samples (1 = без MSAA, 4 = 4x MSAA).
        """
        ...

    @abstractmethod
    def create_shadow_framebuffer(self, size: Tuple[int, int]) -> "FramebufferHandle":
        """
        Создаёт framebuffer для shadow mapping.

        В отличие от обычного framebuffer:
        - Depth texture вместо renderbuffer
        - GL_TEXTURE_COMPARE_MODE для hardware PCF (sampler2DShadow)
        - Нет color attachment
        """
        ...

    @abstractmethod
    def bind_framebuffer(self, framebuffer: "FramebufferHandle | None"):
        """
        Bind custom framebuffer or default (if None).
        """
        ...

    @abstractmethod
    def blit_framebuffer(
        self,
        src: "FramebufferHandle",
        dst: "FramebufferHandle",
        src_rect: Tuple[int, int, int, int],
        dst_rect: Tuple[int, int, int, int],
    ):
        """
        Копирует содержимое src FBO в dst FBO.

        Автоматически выполняет MSAA resolve если src — мультисемплированный.

        Параметры:
            src: Исходный framebuffer.
            dst: Целевой framebuffer.
            src_rect: (x0, y0, x1, y1) прямоугольник источника.
            dst_rect: (x0, y0, x1, y1) прямоугольник назначения.
        """
        ...


class BackendWindow(ABC):
    """Abstract window wrapper."""

    def set_graphics(self, graphics: "GraphicsBackend") -> None:
        """Set graphics backend for framebuffer creation."""
        pass

    @abstractmethod
    def get_window_framebuffer(self) -> "FramebufferHandle | None":
        """Return a handle for the default window framebuffer."""
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
