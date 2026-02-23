"""Backend registry and default implementations."""

from __future__ import annotations
from typing import Optional

from tcbase import Action, Key, MouseButton
from tgfx import (
    GraphicsBackend,
    GPUTextureHandle,
    GPUMeshHandle as MeshHandle,
    ShaderHandle,
    FramebufferHandle,
)
from tgfx.window import BackendWindow, WindowBackend
from .nop_graphics import NOPGraphicsBackend
from .nop_window import NOPWindowBackend
from .qt import QtGLWindowHandle, QtWindowBackend
from termin.visualization.platform.backends.glfw import GLFWWindowBackend

# Use C++ OpenGLGraphicsBackend
from termin.graphics import OpenGLGraphicsBackend

# Context management functions (still in Python)
from termin.visualization.platform.backends.opengl import (
    register_context,
    get_make_current,
)

# SDL backend using C++ implementation
from termin.visualization.platform.backends.sdl import (
    SDLWindowBackend,
    SDLWindowHandle,
)
from termin.visualization.platform.backends.sdl_embedded import (
    SDLEmbeddedWindowBackend,
)

_default_graphics_backend: Optional[GraphicsBackend] = None
_default_window_backend: Optional[WindowBackend] = None


def set_default_graphics_backend(backend: GraphicsBackend):
    global _default_graphics_backend
    _default_graphics_backend = backend


def get_default_graphics_backend() -> GraphicsBackend:
    global _default_graphics_backend
    if _default_graphics_backend is None:
        from tcbase import log
        log.info(f"[get_default_graphics_backend] Creating default backend via get_instance()")
        _default_graphics_backend = OpenGLGraphicsBackend.get_instance()
        log.info(f"[get_default_graphics_backend] Got backend: {_default_graphics_backend}, id={id(_default_graphics_backend)}")
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
    "NOPGraphicsBackend",
    "NOPWindowBackend",
    "QtWindowBackend",
    "QtGLWindowHandle",
    "GLFWWindowBackend",
    "SDLWindowBackend",
    "SDLWindowHandle",
    "SDLEmbeddedWindowBackend",
    "OpenGLGraphicsBackend",
    # Context management
    "register_context",
    "get_make_current",
]
