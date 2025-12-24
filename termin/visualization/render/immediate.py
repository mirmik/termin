"""
ImmediateRenderer - immediate mode rendering for debug visualization, gizmos, etc.

Implemented in C++ for performance. This module re-exports from native.
"""

from termin._native.render import ImmediateRenderer

__all__ = ["ImmediateRenderer"]
