import math

from termin.geombase import (
    AABBf,
    Affine3d,
    Basis3d,
    Bounds2,
    Bounds2f,
    Mat44,
    Quat,
    Ray3,
    RayTriangleHit,
    Rect2f,
    Vec2,
    Vec2f,
    Vec3,
    Vec3f,
    Vec4,
    Vec4f,
)


def test_vector_component_and_checked_operations():
    value = Vec3(2.0, -4.0, 8.0)
    assert value.cwise_product(Vec3(3.0, 0.5, -2.0)) == Vec3(6.0, -2.0, -16.0)
    assert value.cwise_abs() == Vec3(2.0, 4.0, 8.0)
    assert value.to_float().to_double() == value
    assert Vec3(0.0, 0.0, 0.0).try_normalized() is None
    assert Vec2(0.0, 0.0).normalized_or(Vec2(0.0, 1.0), 1.0e-10) == Vec2(0.0, 1.0)
    assert not Vec4(math.inf, 0.0, 0.0, 0.0).is_finite()
    assert Vec4f(1.0, 2.0, 3.0, 4.0).to_double() == Vec4(1.0, 2.0, 3.0, 4.0)


def test_ray_plane_intersection_binding_rejects_invalid_parallel_and_behind_geometry():
    plane_origin = Vec3.zero()
    plane_normal = Vec3.unit_z()
    ray = Ray3(Vec3(1.0, 2.0, 3.0), Vec3(0.0, 0.0, -1.0))
    assert ray.try_intersect_plane(plane_origin, plane_normal) == Vec3(1.0, 2.0, 0.0)

    assert Ray3(Vec3(0.0, 0.0, 1.0), Vec3.unit_x()).try_intersect_plane(plane_origin, plane_normal) is None
    assert ray.try_intersect_plane(plane_origin, Vec3.zero()) is None
    assert ray.try_intersect_plane(plane_origin, Vec3(0.0, 0.0, math.nan)) is None
    assert ray.try_intersect_plane(plane_origin, plane_normal, epsilon=-1.0) is None
    assert Ray3(Vec3(0.0, 0.0, 1.0), Vec3.unit_z()).try_intersect_plane(plane_origin, plane_normal) is None
    assert (
        Ray3(Vec3(0.0, 0.0, 1.0), Vec3.unit_z()).try_intersect_plane(
            plane_origin,
            plane_normal,
            forward_only=False,
        )
        == Vec3.zero()
    )

    ray.origin = Vec3(math.nan, 0.0, 0.0)
    assert ray.try_intersect_plane(plane_origin, plane_normal) is None
    ray.origin = Vec3.zero()
    ray.direction = Vec3.zero()
    assert ray.try_intersect_plane(plane_origin, plane_normal) is None

    zero_direction = Ray3(Vec3(1.0, 2.0, 3.0), Vec3.zero())
    assert zero_direction.direction == Vec3.zero()
    non_finite_direction = Ray3(Vec3(1.0, 2.0, 3.0), Vec3(math.nan, 4.0, 5.0))
    assert math.isnan(non_finite_direction.direction.x)
    assert non_finite_direction.direction.y == 4.0
    assert non_finite_direction.direction.z == 5.0


def test_ray_triangle_intersection_binding_returns_parameter_and_barycentric_coordinates():
    a = Vec3.zero()
    b = Vec3.unit_x()
    c = Vec3.unit_y()
    ray = Ray3(Vec3(0.2, 0.3, 1.0), Vec3(0.0, 0.0, -2.0))

    hit = ray.try_intersect_triangle(a, b, c)
    assert isinstance(hit, RayTriangleHit)
    assert math.isclose(hit.ray_parameter, 1.0)
    assert (hit.barycentric - Vec3(0.5, 0.2, 0.3)).norm() < 1.0e-12
    assert hit.normal == Vec3.unit_z()
    assert ray.point_at(hit.ray_parameter) == Vec3(0.2, 0.3, 0.0)

    reverse_hit = ray.try_intersect_triangle(a, c, b)
    assert reverse_hit is not None
    assert (reverse_hit.barycentric - Vec3(0.5, 0.3, 0.2)).norm() < 1.0e-12
    assert reverse_hit.normal == Vec3.down()
    assert Ray3(Vec3(0.5, 0.0, 1.0), Vec3.down()).try_intersect_triangle(a, b, c) is not None
    vertex_hit = Ray3(a, Vec3.up()).try_intersect_triangle(a, b, c)
    assert vertex_hit is not None
    assert vertex_hit.ray_parameter == 0.0
    assert vertex_hit.barycentric == Vec3(1.0, 0.0, 0.0)

    parameterized_ray = Ray3()
    parameterized_ray.origin = Vec3(0.2, 0.3, 1.0)
    parameterized_ray.direction = Vec3(0.0, 0.0, -0.25)
    parameterized_hit = parameterized_ray.try_intersect_triangle(a, b, c)
    assert parameterized_hit is not None
    assert math.isclose(parameterized_hit.ray_parameter, 4.0)
    assert parameterized_ray.point_at(parameterized_hit.ray_parameter) == Vec3(0.2, 0.3, 0.0)


def test_ray_triangle_intersection_binding_rejects_invalid_geometry_and_is_scale_aware():
    a = Vec3.zero()
    b = Vec3.unit_x()
    c = Vec3.unit_y()
    ray = Ray3(Vec3(0.25, 0.25, 1.0), Vec3.down())

    assert Ray3(Vec3(2.0, 2.0, 1.0), Vec3.down()).try_intersect_triangle(a, b, c) is None
    assert Ray3(Vec3(0.25, 0.25, 1.0), Vec3.unit_x()).try_intersect_triangle(a, b, c) is None
    assert ray.try_intersect_triangle(a, b, Vec3(2.0, 0.0, 0.0)) is None
    assert ray.try_intersect_triangle(a, b, Vec3(0.0, 1.0e-12, 0.0)) is None
    assert ray.try_intersect_triangle(Vec3(math.nan, 0.0, 0.0), b, c) is None
    assert ray.try_intersect_triangle(a, b, c, epsilon=-1.0) is None
    assert ray.try_intersect_triangle(a, b, c, epsilon=math.nan) is None

    assert (
        Ray3(Vec3(0.2, 0.3, 0.0), Vec3(1.0, 0.0, -0.5e-6)).try_intersect_triangle(
            a,
            b,
            c,
            epsilon=1.0e-6,
        )
        is None
    )
    angled_hit = Ray3(Vec3(0.2, 0.3, 0.0), Vec3(1.0, 0.0, -2.0e-6)).try_intersect_triangle(
        a,
        b,
        c,
        epsilon=1.0e-6,
    )
    assert angled_hit is not None
    assert angled_hit.ray_parameter == 0.0

    snapped_hit = Ray3(Vec3(-0.5e-6, 0.5, 1.0), Vec3.down()).try_intersect_triangle(
        a,
        b,
        c,
        epsilon=1.0e-6,
    )
    assert snapped_hit is not None
    assert snapped_hit.barycentric.y == 0.0
    assert (
        Ray3(Vec3(-2.0e-6, 0.5, 1.0), Vec3.down()).try_intersect_triangle(
            a,
            b,
            c,
            epsilon=1.0e-6,
        )
        is None
    )

    near_origin_hit = Ray3(Vec3(0.25, 0.25, 0.5e-6), Vec3.down()).try_intersect_triangle(
        a,
        b,
        c,
        epsilon=1.0e-6,
    )
    assert near_origin_hit is not None
    assert 0.0 < near_origin_hit.ray_parameter < 1.0e-6

    invalid_ray = Ray3(Vec3(0.25, 0.25, 1.0), Vec3.down())
    invalid_ray.direction = Vec3.zero()
    assert invalid_ray.try_intersect_triangle(a, b, c) is None
    invalid_ray.origin = Vec3(0.25, 0.25, 1.0e-300)
    invalid_ray.direction = Vec3(0.0, 0.0, 1.0e300)
    assert invalid_ray.try_intersect_triangle(a, b, c) is None
    invalid_ray.direction = Vec3(0.0, 0.0, -1.0e300)
    assert invalid_ray.try_intersect_triangle(a, b, c) is None
    invalid_ray.origin = Vec3(0.2e-20, 0.3e-20, 1.0e-20)
    assert (
        invalid_ray.try_intersect_triangle(
            a,
            Vec3(1.0e-20, 0.0, 0.0),
            Vec3(0.0, 1.0e-20, 0.0),
        )
        is None
    )

    behind_ray = Ray3(Vec3(0.25, 0.25, -1.0), Vec3.up())
    behind = (Vec3(0.0, 0.0, -2.0), Vec3(1.0, 0.0, -2.0), Vec3(0.0, 1.0, -2.0))
    assert behind_ray.try_intersect_triangle(*behind) is None
    behind_hit = behind_ray.try_intersect_triangle(*behind, forward_only=False)
    assert behind_hit is not None
    assert math.isclose(behind_hit.ray_parameter, -1.0)

    for scale in (1.0e-120, 1.0e120):
        scaled_hit = Ray3(Vec3(0.2 * scale, 0.3 * scale, scale), Vec3.down()).try_intersect_triangle(
            a,
            Vec3(scale, 0.0, 0.0),
            Vec3(0.0, scale, 0.0),
        )
        assert scaled_hit is not None
        assert math.isclose(scaled_hit.ray_parameter / scale, 1.0, rel_tol=1.0e-12)
        assert (scaled_hit.barycentric - Vec3(0.5, 0.2, 0.3)).norm() < 1.0e-12


def test_affine_checked_inverse_normal_and_centered_inverse_transform_bindings():
    for uniform_scale in (1.0e-6, 1.0e6):
        basis = Basis3d.scaling(uniform_scale)
        inverse = basis.try_inverse()
        assert inverse is not None
        product = basis @ inverse
        assert product.x == Vec3.unit_x()
        assert product.y == Vec3.unit_y()
        assert product.z == Vec3.unit_z()

    mixed_axes = Basis3d.from_quat(Quat.from_axis_angle(Vec3.unit_z(), math.pi / 4.0))
    unreliable = mixed_axes @ Basis3d.scaling(1.0e-16, 1.0e16, 1.0) @ mixed_axes
    assert unreliable.try_inverse() is None
    assert Basis3d.identity().try_inverse(epsilon=-1.0) is None
    assert Basis3d.identity().try_inverse(epsilon=math.nan) is None

    oriented_nonuniform = Basis3d.from_quat(
        Quat.from_axis_angle(Vec3(1.0, 2.0, -0.5).normalized(), 0.71)
    ) @ Basis3d.scaling(2.0, 3.0, 4.0)
    local_tangent0 = Vec3(1.0, 2.0, -0.5)
    local_tangent1 = Vec3(-0.3, 0.4, 1.2)
    local_normal = local_tangent0.cross(local_tangent1)
    transformed_normal = oriented_nonuniform.try_transform_normal(local_normal)
    assert transformed_normal is not None
    assert abs(transformed_normal.dot(oriented_nonuniform.transform_vector(local_tangent0))) < 1.0e-12
    assert abs(transformed_normal.dot(oriented_nonuniform.transform_vector(local_tangent1))) < 1.0e-12
    assert Basis3d.scaling(2.0, 3.0, 4.0).try_transform_normal(Vec3(0.0, 0.0, 2.0)) == Vec3(0.0, 0.0, 0.5)
    assert Basis3d.scaling(1.0, 0.0, 1.0).try_transform_normal(Vec3.unit_z()) is None
    assert Basis3d.identity().try_transform_normal(Vec3(math.nan, 0.0, 0.0)) is None
    assert Basis3d.identity().try_transform_normal(Vec3.unit_z(), epsilon=-1.0) is None

    affine = Affine3d(oriented_nonuniform, Vec3(1.0e12, -2.0e12, 3.0e12))
    affine_normal = affine.try_transform_normal(local_normal)
    assert affine_normal is not None
    assert (affine_normal - transformed_normal).norm() < 1.0e-12

    local_point = Vec3(0.25, -0.5, 1.75)
    world_point = affine.transform_point(local_point)
    recovered_point = affine.try_inverse_transform_point(world_point)
    assert recovered_point is not None
    assert (recovered_point - local_point).norm() < 5.0e-4

    local_vector = Vec3(-0.5, 0.75, 0.125)
    world_vector = affine.transform_vector(local_vector)
    recovered_vector = affine.try_inverse_transform_vector(world_vector)
    assert recovered_vector is not None
    assert (recovered_vector - local_vector).norm() < 1.0e-12

    singular = Affine3d.scaling(1.0, 0.0, 1.0)
    assert singular.try_transform_normal(Vec3.unit_z()) is None
    assert singular.try_inverse_transform_point(world_point) is None
    assert singular.try_inverse_transform_vector(world_vector) is None
    assert affine.try_inverse_transform_point(Vec3(math.inf, 0.0, 0.0)) is None
    assert affine.try_inverse_transform_vector(Vec3(math.nan, 0.0, 0.0)) is None


def test_bounds_rect_and_float_aabb_bindings():
    bounds = Bounds2(1.0, 2.0, 5.0, 8.0)
    assert bounds.is_valid()
    assert bounds.contains_closed(Vec2(5.0, 8.0))
    assert not bounds.contains_half_open(Vec2(5.0, 8.0))
    bounds.extend(Vec2(-2.0, 10.0))
    assert bounds.min() == Vec2(-2.0, 2.0)
    assert bounds.max() == Vec2(5.0, 10.0)
    assert bounds.try_intersection(Bounds2(4.0, 0.0, 10.0, 4.0)).min() == Vec2(4.0, 2.0)

    bounds_f = Bounds2f(1.0, 2.0, 5.0, 8.0)
    bounds_f.extend(Vec2f(-2.0, 10.0))
    assert bounds_f.min() == Vec2f(-2.0, 2.0)
    assert bounds_f.max() == Vec2f(5.0, 10.0)

    rect = Rect2f(1.0, 2.0, 4.0, 6.0)
    assert rect.is_valid()
    assert rect.bounds().to_rect().size() == Vec2(4.0, 6.0).to_float()

    aabb = AABBf(Vec3f(-1.0, -2.0, -3.0), Vec3f(4.0, 5.0, 6.0))
    assert aabb.is_valid()
    assert aabb.project_point(Vec3f(20.0, 0.0, 0.0)) == Vec3f(4.0, 0.0, 0.0)


def test_matrix_homogeneous_and_checked_operations():
    matrix = Mat44.translation(Vec3(3.0, -2.0, 7.0))
    assert matrix.transform_homogeneous(Vec4(1.0, 2.0, 3.0, 1.0)) == Vec4(4.0, 0.0, 10.0, 1.0)
    assert Mat44.zero().try_transform_point(Vec3(1.0, 2.0, 3.0)) is None
    assert Mat44.scale(Vec3(1.0, 0.0, 1.0)).try_inverse() is None

    matrix_f = matrix.to_float()
    transformed = matrix_f.transform_point(Vec3f(1.0, 2.0, 3.0))
    assert transformed == Vec3f(4.0, 0.0, 10.0)
    assert matrix_f.transform_homogeneous(Vec4f(1.0, 2.0, 3.0, 1.0)) == Vec4f(4.0, 0.0, 10.0, 1.0)
    assert isinstance(matrix_f.to_double(), Mat44)
