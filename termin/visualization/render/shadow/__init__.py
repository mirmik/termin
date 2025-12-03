"""Модуль для shadow mapping."""

from termin.visualization.render.shadow.shadow_camera import (
    ShadowCameraParams,
    build_shadow_view_matrix,
    build_shadow_projection_matrix,
    compute_light_space_matrix,
)

__all__ = [
    "ShadowCameraParams",
    "build_shadow_view_matrix",
    "build_shadow_projection_matrix",
    "compute_light_space_matrix",
]
