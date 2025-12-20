"""GeneralTransform3 - Transform using GeneralPose3 with scale inheritance.

Uses C++ native implementation for performance.
"""

from termin.geombase._geom_native import (
    GeneralTransform3,
    GeneralTransform3Pool,
    TransformHandle,
)

__all__ = ['GeneralTransform3', 'GeneralTransform3Pool', 'TransformHandle']
