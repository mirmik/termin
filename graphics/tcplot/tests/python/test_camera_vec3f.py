from termin.geombase import AABB, Vec3
from termin.plot._plot_native import OrbitCamera


def test_plot_camera_uses_shared_projection_and_axis_convention():
    import numpy as np
    import pytest
    from termin.geombase import CameraProjection
    from termin.plot import CameraProjection as PlotProjection

    assert PlotProjection is CameraProjection
    camera = OrbitCamera()
    camera.azimuth = camera.elevation = 0
    view = np.array(camera.view_matrix()).reshape((4, 4), order="F")
    eye = camera.eye
    assert view @ np.array([eye.x, eye.y + 1, eye.z, 1]) == pytest.approx([0, 1, 0, 1])
    camera.set_isometric()
    assert camera.projection_type == CameraProjection.Orthographic
    camera.fit_bounds(AABB(Vec3(-1, -1, -1), Vec3(1, 1, 1)), 0.4)
    before = camera.ortho_size
    distance = camera.distance
    camera.zoom(0.5)
    assert camera.ortho_size == pytest.approx(before * 0.5)
    assert camera.distance == distance


def test_orbit_camera_double_precision_api():
    camera = OrbitCamera()

    camera.target = Vec3(1.0, 2.0, 3.0)
    assert isinstance(camera.target, Vec3)
    assert camera.target.approx_eq(Vec3(1.0, 2.0, 3.0))

    camera.fit_bounds(AABB(Vec3(-1.0, -1.0, -1.0), Vec3(1.0, 1.0, 1.0)))

    assert isinstance(camera.target, Vec3)
    assert isinstance(camera.eye, Vec3)
