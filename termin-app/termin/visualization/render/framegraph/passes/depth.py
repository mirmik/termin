"""Depth passes - linear depth rendering passes.

Re-exports C++ DepthPass variants.
"""
from termin.render_components import (
    ColorToDepthPass,
    DepthOnlyPass,
    DepthPass,
    DepthToColorPass,
)

__all__ = [
    "ColorToDepthPass",
    "DepthOnlyPass",
    "DepthPass",
    "DepthToColorPass",
]
