"""OpenGL-based graphics backend."""

from __future__ import annotations

import ctypes
from typing import Dict, Tuple

import numpy as np
from OpenGL import GL as gl
from OpenGL import GL as GL
from OpenGL.raw.GL.VERSION.GL_2_0 import glVertexAttribPointer as _gl_vertex_attrib_pointer

from termin.mesh.mesh import Mesh, VertexAttribType

from termin.visualization.platform.backends.base import (
    FramebufferHandle,
    GraphicsBackend,
    GPUTextureHandle,
    MeshHandle,
    PolylineHandle,
    ShaderHandle,
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
