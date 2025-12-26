"""Graphics module - graphics backend and GPU resource handles."""

# Setup DLL paths before importing native extensions
from termin import _dll_setup  # noqa: F401

from termin.graphics._graphics_native import (
    # Types
    Color4,
    Size2i,
    Rect2i,
    # Render state
    PolygonMode,
    BlendFactor,
    DepthFunc,
    RenderState,
    # GPU handles
    ShaderHandle,
    GPUMeshHandle,
    GPUTextureHandle,
    FramebufferHandle,
    # Graphics backends
    GraphicsBackend,
    OpenGLGraphicsBackend,
    # Draw mode
    DrawMode,
    # Functions
    init_opengl,
)

__all__ = [
    "Color4",
    "Size2i",
    "Rect2i",
    "PolygonMode",
    "BlendFactor",
    "DepthFunc",
    "RenderState",
    "ShaderHandle",
    "GPUMeshHandle",
    "GPUTextureHandle",
    "FramebufferHandle",
    "GraphicsBackend",
    "OpenGLGraphicsBackend",
    "DrawMode",
    "init_opengl",
]
