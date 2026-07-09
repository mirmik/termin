from array import array

import numpy as np

from termin.geombase import Bounds2f, Vec3
from termin.render_passes import (
    ShadowCameraParams,
    build_shadow_projection_matrix,
    build_shadow_view_matrix,
    compute_frustum_corners,
    compute_light_space_matrix,
)


def _matrix_memoryview(values):
    return memoryview(array("d", values)).cast("B").cast("d", shape=(4, 4))


def test_shadow_camera_helpers_are_exported_from_render_passes():
    params = ShadowCameraParams(
        Vec3(0.0, -1.0, -1.0),
        ortho_bounds=Bounds2f(-2.0, -1.0, 2.0, 1.0),
        near=0.5,
        far=25.0,
    )

    assert isinstance(params.light_direction, Vec3)
    assert isinstance(params.center, Vec3)
    assert params.ortho_bounds == Bounds2f(-2.0, -1.0, 2.0, 1.0)
    assert build_shadow_view_matrix(params).shape == (4, 4)
    assert build_shadow_projection_matrix(params).shape == (4, 4)
    assert compute_light_space_matrix(params).shape == (4, 4)

    params.light_direction = Vec3(1.0, 0.0, 0.0)
    params.center = Vec3(2.0, 3.0, 4.0)

    assert params.light_direction == Vec3(1.0, 0.0, 0.0)
    assert params.center == Vec3(2.0, 3.0, 4.0)

    params.ortho_bounds = None
    assert params.ortho_bounds is None

    params.ortho_bounds = Bounds2f(-4.0, -3.0, 4.0, 3.0)
    assert params.ortho_bounds == Bounds2f(-4.0, -3.0, 4.0, 3.0)


def test_shadow_camera_frustum_helpers_accept_buffer_compatible_matrices():
    values = np.eye(4, dtype=np.float64)
    corners_from_numpy = compute_frustum_corners(values, values)

    matrix = _matrix_memoryview(values.reshape(-1).tolist())
    corners_from_memoryview = compute_frustum_corners(matrix, matrix)

    assert corners_from_numpy.shape == (8, 3)
    np.testing.assert_allclose(corners_from_memoryview, corners_from_numpy)
