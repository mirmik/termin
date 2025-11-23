"""Backend registry and default implementations."""

from __future__ import annotations
from typing import Optional


from .base import (
    Action,
    BackendWindow,
    GraphicsBackend,
    Key,
    MeshHandle,
    MouseButton,
    PolylineHandle,
    ShaderHandle,
    TextureHandle,
    WindowBackend,
    FramebufferHandle,
)
from .nop_graphics import NOPGraphicsBackend
from .nop_window import NOPWindowBackend

from .qt import QtGLWindowHandle
from .opengl import OpenGLGraphicsBackend
from .qt import QtWindowBackend

_default_graphics_backend: Optional[GraphicsBackend] = None
_default_window_backend: Optional[WindowBackend] = None


def set_default_graphics_backend(backend: GraphicsBackend):
    global _default_graphics_backend
    _default_graphics_backend = backend


def get_default_graphics_backend() -> Optional[GraphicsBackend]:
    return _default_graphics_backend


def set_default_window_backend(backend: WindowBackend):
    global _default_window_backend
    _default_window_backend = backend


def get_default_window_backend() -> Optional[WindowBackend]:
    return _default_window_backend


__all__ = [
    "Action",
    "BackendWindow",
    "GraphicsBackend",
    "Key",
    "MeshHandle",
    "MouseButton",
    "PolylineHandle",
    "ShaderHandle",
    "TextureHandle",
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
    "OpenGLGraphicsBackend",
]
