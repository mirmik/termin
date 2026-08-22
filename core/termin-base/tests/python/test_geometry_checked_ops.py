import math

from termin.geombase import AABBf, Bounds2, Bounds2f, Mat44, Rect2f, Vec2, Vec2f, Vec3, Vec3f, Vec4, Vec4f


def test_vector_component_and_checked_operations():
    value = Vec3(2.0, -4.0, 8.0)
    assert value.cwise_product(Vec3(3.0, 0.5, -2.0)) == Vec3(6.0, -2.0, -16.0)
    assert value.cwise_abs() == Vec3(2.0, 4.0, 8.0)
    assert value.to_float().to_double() == value
    assert Vec3(0.0, 0.0, 0.0).try_normalized() is None
    assert Vec2(0.0, 0.0).normalized_or(Vec2(0.0, 1.0), 1.0e-10) == Vec2(0.0, 1.0)
    assert not Vec4(math.inf, 0.0, 0.0, 0.0).is_finite()
    assert Vec4f(1.0, 2.0, 3.0, 4.0).to_double() == Vec4(1.0, 2.0, 3.0, 4.0)


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
