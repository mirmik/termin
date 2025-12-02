"""OpenGL helpers and backend bindings."""

# OpenGLGraphicsBackend теперь живёт в platform/backends/opengl.py
from termin.visualization.platform.backends.opengl import OpenGLGraphicsBackend
from termin.visualization.render.opengl.helpers import init_opengl, opengl_is_inited

__all__ = [
    "OpenGLGraphicsBackend",
    "init_opengl",
    "opengl_is_inited",
]
