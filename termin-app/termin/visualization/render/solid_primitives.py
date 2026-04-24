"""
SolidPrimitiveRenderer - efficient solid primitive rendering using pre-built unit meshes.

Implemented in C++ for performance. This module re-exports from native.
"""

from termin._native.render import SolidPrimitiveRenderer

__all__ = ["SolidPrimitiveRenderer"]
