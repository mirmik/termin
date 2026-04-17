"""Graphics module — project-level render settings + a few tgfx
primitives that non-rendering subsystems still reference (RenderState
for navmesh/voxels, Color4 for UI debug overlays).

The legacy rendering path (OpenGLGraphicsBackend, FramebufferHandle,
ShaderHandle, GPUTextureHandle, GraphicsBackend, …) is gone.
"""

from tgfx import (
    Color4,
    RenderState,
)

from termin._native import (
    RenderSyncMode,
    get_render_sync_mode,
    set_render_sync_mode,
)

__all__ = [
    "Color4",
    "RenderState",
    "RenderSyncMode",
    "get_render_sync_mode",
    "set_render_sync_mode",
]
