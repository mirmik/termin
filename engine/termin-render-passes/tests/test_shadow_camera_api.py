from array import array

import numpy as np
import pytest

from termin.geombase import Bounds2f, Vec3
from termin.render_passes import (
    ShadowCameraParams,
    build_shadow_projection_matrix,
    build_shadow_view_matrix,
    compute_frustum_corners,
    compute_light_space_matrix,
    fit_shadow_frustum_to_camera,
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


def test_shadow_camera_frustum_inverse_handles_large_world_translation():
    near = 0.1
    far = 1000.0
    aspect = 16.0 / 9.0
    f = 1.0 / np.tan(np.deg2rad(60.0) * 0.5)
    projection = np.array(
        [
            [f / aspect, 0.0, 0.0, 0.0],
            [0.0, 0.0, -f, 0.0],
            [0.0, far / (far - near), 0.0, -(far * near) / (far - near)],
            [0.0, 1.0, 0.0, 0.0],
        ],
        dtype=np.float64,
    )
    view = np.eye(4, dtype=np.float64)
    view[0, 3] = -1_000_000.0

    corners = compute_frustum_corners(view, projection)

    assert np.isfinite(corners).all()
    assert abs(float(corners[:, 0].mean()) - 1_000_000.0) < 10.0


def test_shadow_camera_frustum_failure_is_explicit():
    singular = np.zeros((4, 4), dtype=np.float64)

    with pytest.raises(ValueError, match="cannot be inverted"):
        compute_frustum_corners(singular, singular)

    with pytest.raises(ValueError, match="cannot be fitted"):
        fit_shadow_frustum_to_camera(singular, singular, Vec3(0.0, -1.0, -1.0))


@pytest.mark.parametrize(
    ("light_direction", "kwargs"),
    [
        (Vec3(0.0, 0.0, 0.0), {}),
        (Vec3(float("nan"), -1.0, 0.0), {}),
        (Vec3(0.0, -1.0, -1.0), {"padding": float("nan")}),
        (Vec3(0.0, -1.0, -1.0), {"padding": -1.0}),
        (Vec3(0.0, -1.0, -1.0), {"padding": float(np.finfo(np.float32).max)}),
        (Vec3(0.0, -1.0, -1.0), {"shadow_map_resolution": 0}),
        (Vec3(0.0, -1.0, -1.0), {"caster_offset": float("inf")}),
        (Vec3(0.0, -1.0, -1.0), {"caster_offset": -1.0}),
    ],
)
def test_shadow_camera_fit_rejects_invalid_domain(light_direction, kwargs):
    identity = np.eye(4, dtype=np.float64)

    with pytest.raises(ValueError, match="cannot be fitted"):
        fit_shadow_frustum_to_camera(identity, identity, light_direction, **kwargs)
