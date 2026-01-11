"""
Shadow camera implementation for directional light shadow mapping.

Core math functions are implemented in C++. This module provides
a convenience wrapper for Camera integration.

Coordinate convention: Y-forward, Z-up (same as main engine)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

# Re-export C++ implementations
from termin._native.render import (
    ShadowCameraParams,
    build_shadow_view_matrix,
    build_shadow_projection_matrix,
    compute_light_space_matrix,
    compute_frustum_corners,
    fit_shadow_frustum_to_camera as _fit_shadow_frustum_to_camera,
)

if TYPE_CHECKING:
    from termin.visualization.core.camera import Camera

__all__ = [
    "ShadowCameraParams",
    "build_shadow_view_matrix",
    "build_shadow_projection_matrix",
    "compute_light_space_matrix",
    "compute_frustum_corners",
    "fit_shadow_frustum_to_camera",
]


def _limit_projection_far(
    proj: np.ndarray,
    camera: "Camera",
    max_distance: float,
) -> np.ndarray:
    """
    Create a copy of projection matrix with limited far plane.

    Handles both perspective and orthographic projections (Y-forward convention).
    """
    proj = proj.copy()

    near = camera.near
    far = min(camera.far, max_distance)

    if far <= near:
        far = near + 1.0

    # Check projection type
    projection_type = getattr(camera, 'projection_type', 'perspective')

    if projection_type == "orthographic":
        # For Y-forward orthographic projection:
        # proj[2,1] = 2.0 / (far - near)
        # proj[2,3] = -(far + near) / (far - near)
        proj[2, 1] = 2.0 / (far - near)
        proj[2, 3] = -(far + near) / (far - near)
    else:
        # For Y-forward perspective projection:
        # proj[2,1] = (far + near) / (far - near)
        # proj[2,3] = -2 * far * near / (far - near)
        proj[2, 1] = (far + near) / (far - near)
        proj[2, 3] = -2.0 * far * near / (far - near)

    return proj


def fit_shadow_frustum_to_camera(
    camera: "Camera",
    light_direction: np.ndarray,
    padding: float = 1.0,
    max_shadow_distance: float | None = None,
    shadow_map_resolution: int = 1024,
    stabilize: bool = True,
    caster_offset: float = 50.0,
) -> ShadowCameraParams:
    """
    Compute shadow camera parameters that cover the camera's view frustum.

    Algorithm:
    1. Compute 8 frustum corners in world space
    2. Transform to light space (light orientation)
    3. Find AABB in light space
    4. Use AABB as orthographic projection bounds
    5. (Optional) Stabilize bounds to prevent shadow jittering

    Parameters:
        camera: Main scene camera
        light_direction: Directional light direction
        padding: Extra padding around frustum
        max_shadow_distance: Max shadow distance (None = use camera far plane)
        shadow_map_resolution: Shadow map resolution (for stabilization)
        stabilize: Enable texel snapping to prevent shadow jittering
        caster_offset: Distance behind camera to capture shadow casters

    Returns:
        ShadowCameraParams with fitted frustum
    """
    light_direction = np.asarray(light_direction, dtype=np.float64)
    norm = np.linalg.norm(light_direction)
    if norm > 1e-6:
        light_direction = light_direction / norm

    view = camera.get_view_matrix().to_numpy()
    proj = camera.get_projection_matrix().to_numpy()

    if max_shadow_distance is not None:
        proj = _limit_projection_far(proj, camera, max_shadow_distance)

    return _fit_shadow_frustum_to_camera(
        view,
        proj,
        light_direction,
        padding,
        shadow_map_resolution,
        stabilize,
        caster_offset,
    )
