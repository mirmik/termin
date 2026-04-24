"""Модуль для shadow mapping."""

from termin.visualization.render.shadow.shadow_camera import (
    ShadowCameraParams,
    build_shadow_view_matrix,
    build_shadow_projection_matrix,
    compute_light_space_matrix,
)
# ShadowMapArrayResource и ShadowMapArrayEntry перенесены в framegraph.resource
from termin.visualization.render.framegraph.resource import (
    ShadowMapArrayEntry,
    ShadowMapArrayResource,
)

__all__ = [
    "ShadowCameraParams",
    "build_shadow_view_matrix",
    "build_shadow_projection_matrix",
    "compute_light_space_matrix",
    "ShadowMapArrayEntry",
    "ShadowMapArrayResource",
]
