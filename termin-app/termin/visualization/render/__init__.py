"""Rendering package entry point. Import concrete submodules directly."""

# Import to ensure GLSL preprocessor fallback loader is set up before any shader compilation
import termin.visualization.render.glsl_preprocessor  # noqa: F401

from termin._native.render import RenderEngine
from termin.visualization.render.manager import RenderingManager
from termin.visualization.render.offscreen_context import OffscreenContext
from termin.visualization.render.surface import SDLWindowRenderSurface
from termin.visualization.render.view import RenderView

__all__ = [
    "RenderEngine",
    "RenderingManager",
    "OffscreenContext",
    "SDLWindowRenderSurface",
    "RenderView",
]
