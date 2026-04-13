"""
RenderSurface — абстракция целевой поверхности рендеринга.

C++ SDLWindowRenderSurface используется для всех окон.
"""

from termin.display._platform_native import SDLWindowRenderSurface, SDLWindowBackend

__all__ = ["SDLWindowRenderSurface", "SDLWindowBackend"]
