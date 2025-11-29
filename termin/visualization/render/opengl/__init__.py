"""OpenGL helpers and backend bindings."""

from termin.visualization.render.opengl.backends import OpenGLGraphicsBackend
from termin.visualization.render.opengl.helpers import init_opengl, opengl_is_inited

__all__ = [
    "OpenGLGraphicsBackend",
    "init_opengl",
    "opengl_is_inited",
]
