"""OpenGL-based graphics backend.

DEPRECATED: Этот модуль перенесён в termin.visualization.platform.backends.opengl
Данный файл сохранён для обратной совместимости.
"""

# Реэкспорт из нового места
from termin.visualization.platform.backends.opengl import (
    OpenGLGraphicsBackend,
    OpenGLShaderHandle,
    OpenGLMeshHandle,
    OpenGLPolylineHandle,
    OpenGLTextureHandle,
    OpenGLFramebufferHandle,
    GL_TYPE_MAP,
)

__all__ = [
    "OpenGLGraphicsBackend",
    "OpenGLShaderHandle",
    "OpenGLMeshHandle",
    "OpenGLPolylineHandle",
    "OpenGLTextureHandle",
    "OpenGLFramebufferHandle",
    "GL_TYPE_MAP",
]
