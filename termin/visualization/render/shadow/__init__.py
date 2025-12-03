"""Модуль для shadow mapping."""

from termin.visualization.render.shadow.shadow_camera import (
    ShadowCameraParams,
    build_shadow_view_matrix,
    build_shadow_projection_matrix,
    compute_light_space_matrix,
)
from termin.visualization.render.shadow.shadow_map_array import (
    ShadowMapEntry,
    ShadowMapArray,
)

__all__ = [
    "ShadowCameraParams",
    "build_shadow_view_matrix",
    "build_shadow_projection_matrix",
    "compute_light_space_matrix",
    "ShadowMapEntry",
    "ShadowMapArray",
]
