from termin.geombase import Vec3
from termin.render_passes import (
    ShadowCameraParams,
    build_shadow_projection_matrix,
    build_shadow_view_matrix,
    compute_light_space_matrix,
)


def test_shadow_camera_helpers_are_exported_from_render_passes():
    params = ShadowCameraParams(
        Vec3(0.0, -1.0, -1.0),
        ortho_bounds=(-2.0, 2.0, -1.0, 1.0),
        near=0.5,
        far=25.0,
    )

    assert isinstance(params.light_direction, Vec3)
    assert isinstance(params.center, Vec3)
    assert params.ortho_bounds == (-2.0, 2.0, -1.0, 1.0)
    assert build_shadow_view_matrix(params).shape == (4, 4)
    assert build_shadow_projection_matrix(params).shape == (4, 4)
    assert compute_light_space_matrix(params).shape == (4, 4)

    params.light_direction = Vec3(1.0, 0.0, 0.0)
    params.center = Vec3(2.0, 3.0, 4.0)

    assert params.light_direction == Vec3(1.0, 0.0, 0.0)
    assert params.center == Vec3(2.0, 3.0, 4.0)
