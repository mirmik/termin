"""
RenderSurface — абстракция целевой поверхности рендеринга.

C++ SDLWindowRenderSurface используется для всех окон.
"""

from termin._native.platform import SDLWindowRenderSurface, SDLWindowBackend

__all__ = ["SDLWindowRenderSurface", "SDLWindowBackend"]
