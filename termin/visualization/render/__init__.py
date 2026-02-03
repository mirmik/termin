"""Rendering package entry point. Import concrete submodules directly."""

# Import to ensure GLSL preprocessor fallback loader is set up before any shader compilation
import termin.visualization.render.glsl_preprocessor  # noqa: F401

from termin._native.render import RenderEngine
from termin.visualization.render.headless import HeadlessContext
from termin.visualization.render.manager import RenderingManager
from termin.visualization.render.offscreen_context import OffscreenContext
from termin.visualization.render.surface import SDLWindowRenderSurface
from termin.visualization.render.view import RenderView
from termin.visualization.render.state import ViewportRenderState

__all__ = [
    "RenderEngine",
    "HeadlessContext",
    "RenderingManager",
    "OffscreenContext",
    "SDLWindowRenderSurface",
    "RenderView",
    "ViewportRenderState",
]
