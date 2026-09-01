"""Screen-space 2D text rendering - re-export of the C++ Text2DRenderer.

The renderer itself lives in C++ (termin-graphics/src/tgfx2/
text2d_renderer.cpp, bound in _graphics_native). This module is kept only
so existing ``from termin.graphics.text2d import Text2DRenderer`` imports keep
working; new code may import directly from ``termin.graphics._graphics_native``.
"""
from __future__ import annotations

from termin.graphics._graphics_native import Text2DRenderer

__all__ = ["Text2DRenderer"]
