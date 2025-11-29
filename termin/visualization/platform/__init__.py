"""Platform-specific windowing and backend glue."""

from termin.visualization.platform.window import Window
from termin.visualization.platform.backends import (
    Action,
    BackendWindow,
    GraphicsBackend,
    Key,
    MouseButton,
    OpenGLGraphicsBackend,
    WindowBackend,
    get_default_graphics_backend,
    get_default_window_backend,
    set_default_graphics_backend,
    set_default_window_backend,
)

__all__ = [
    "Window",
    "Action",
    "BackendWindow",
    "GraphicsBackend",
    "Key",
    "MouseButton",
    "WindowBackend",
    "OpenGLGraphicsBackend",
    "get_default_graphics_backend",
    "get_default_window_backend",
    "set_default_graphics_backend",
    "set_default_window_backend",
]
