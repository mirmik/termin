from termin.geombase import AABB, Vec3
from tcplot._tcplot_native import OrbitCamera


def test_orbit_camera_double_precision_api():
    camera = OrbitCamera()

    camera.target = Vec3(1.0, 2.0, 3.0)
    assert isinstance(camera.target, Vec3)
    assert camera.target.approx_eq(Vec3(1.0, 2.0, 3.0))

    camera.fit_bounds(AABB(Vec3(-1.0, -1.0, -1.0), Vec3(1.0, 1.0, 1.0)))

    assert isinstance(camera.target, Vec3)
    assert isinstance(camera.eye, Vec3)
