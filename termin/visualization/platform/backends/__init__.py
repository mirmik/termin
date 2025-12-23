"""Backend registry and default implementations."""

from __future__ import annotations
from typing import Optional

from .base import (
    Action,
    BackendWindow,
    GraphicsBackend,
    GPUTextureHandle,
    Key,
    MeshHandle,
    MouseButton,
    ShaderHandle,
    WindowBackend,
    FramebufferHandle,
)
from .nop_graphics import NOPGraphicsBackend
from .nop_window import NOPWindowBackend
from .qt import QtGLWindowHandle, QtWindowBackend
from termin.visualization.platform.backends.glfw import GLFWWindowBackend
from termin.visualization.platform.backends.opengl import OpenGLGraphicsBackend

# Optional SDL backend (requires PySDL2)
try:
    from termin.visualization.platform.backends.sdl import SDLWindowBackend, SDLWindowHandle
    from termin.visualization.platform.backends.sdl_embedded import (
        SDLEmbeddedWindowBackend,
        SDLEmbeddedWindowHandle,
    )
except ImportError:
    SDLWindowBackend = None  # type: ignore
    SDLWindowHandle = None  # type: ignore
    SDLEmbeddedWindowBackend = None  # type: ignore
    SDLEmbeddedWindowHandle = None  # type: ignore

_default_graphics_backend: Optional[GraphicsBackend] = None
_default_window_backend: Optional[WindowBackend] = None


def set_default_graphics_backend(backend: GraphicsBackend):
    global _default_graphics_backend
    _default_graphics_backend = backend


def get_default_graphics_backend() -> GraphicsBackend:
    global _default_graphics_backend
    if _default_graphics_backend is None:
        _default_graphics_backend = OpenGLGraphicsBackend()
    return _default_graphics_backend


def set_default_window_backend(backend: WindowBackend):
    global _default_window_backend
    _default_window_backend = backend


def get_default_window_backend() -> WindowBackend:
    global _default_window_backend
    if _default_window_backend is None:
        _default_window_backend = GLFWWindowBackend()
    return _default_window_backend


__all__ = [
    "Action",
    "BackendWindow",
    "GraphicsBackend",
    "Key",
    "MeshHandle",
    "MouseButton",
    "ShaderHandle",
    "GPUTextureHandle",
    "WindowBackend",
    "FramebufferHandle",
    "set_default_graphics_backend",
    "get_default_graphics_backend",
    "set_default_window_backend",
    "get_default_window_backend",
    "NOPGraphicsBackend",   # <-- экспортируем
    "NOPWindowBackend",     # <-- экспортируем
    "QtWindowBackend",
    "QtGLWindowHandle",
    "GLFWWindowBackend",
    "SDLWindowBackend",
    "SDLWindowHandle",
    "SDLEmbeddedWindowBackend",
    "SDLEmbeddedWindowHandle",
    "OpenGLGraphicsBackend",
]
