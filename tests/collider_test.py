import unittest
import numpy as np
from termin.colliders import (
    CapsuleCollider, SphereCollider, BoxCollider,
    UnionCollider, AttachedCollider
)
from termin.geombase import GeneralTransform3, Ray3
from termin.geombase._geom_native import Vec3


def vec3_to_np(v: Vec3) -> np.ndarray:
    return np.array([v.x, v.y, v.z])


class TestCollider(unittest.TestCase):
    def test_closest_to_capsule(self):
        capsule1 = CapsuleCollider(
            Vec3(0.0, 0.0, 0.0),
            Vec3(0.0, 0.0, 1.0),
            0.25
        )
        capsule2 = CapsuleCollider(
            Vec3(1.0, 0.0, 0.0),
            Vec3(1.0, 0.0, 0.0),
            0.25
        )

        hit = capsule1.closest_to_collider(capsule2)

        expected_dist = 0.5  # Capsules are touching
        self.assertAlmostEqual(hit.distance, expected_dist)

        expected_p_near = np.array([0.25, 0.0, 0.0])
        expected_q_near = np.array([0.75, 0.0, 0.0])

        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_a), expected_p_near)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_b), expected_q_near)

    def test_closest_sphere_to_capsule(self):
        capsule = CapsuleCollider(
            Vec3(0.0, 0.0, 0.0),
            Vec3(0.0, 0.0, 2.0),
            0.5
        )
        sphere = SphereCollider(
            Vec3(1.0, 0.0, 1.0),
            0.5
        )

        hit = sphere.closest_to_collider(capsule)

        expected_dist = 0.0  # They are touching
        self.assertAlmostEqual(hit.distance, expected_dist)

        expected_p_near = np.array([0.5, 0.0, 1.0])
        expected_q_near = np.array([0.5, 0.0, 1.0])

        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_a), expected_p_near)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_b), expected_q_near)

    def test_closest_union_collider(self):
        sphere1 = SphereCollider(Vec3(0.0, 0.0, 0.0), 0.5)
        sphere2 = SphereCollider(Vec3(3.0, 0.0, 0.0), 0.5)
        union_collider = UnionCollider([sphere1, sphere2])

        test_sphere = SphereCollider(Vec3(0.0, 1.5, 0.0), 0.5)

        hit = union_collider.closest_to_collider(test_sphere)

        expected_dist = 0.5  # Closest to sphere1
        self.assertAlmostEqual(hit.distance, expected_dist)

        expected_p_near = np.array([0.0, 0.5, 0.0])
        expected_q_near = np.array([0.0, 1.0, 0.0])

        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_a), expected_p_near)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_b), expected_q_near)

    def test_two_union_colliders(self):
        sphere1 = SphereCollider(Vec3(0.0, 0.0, 0.0), 0.5)
        sphere2 = SphereCollider(Vec3(3.0, 0.0, 0.0), 0.5)
        union_collider1 = UnionCollider([sphere1, sphere2])

        sphere3 = SphereCollider(Vec3(1.25, 0.0, 0.0), 0.5)
        sphere4 = SphereCollider(Vec3(5.0, 0.0, 0.0), 0.5)
        union_collider2 = UnionCollider([sphere3, sphere4])

        hit = union_collider1.closest_to_collider(union_collider2)

        expected_dist = 0.25  # Closest between sphere1 and sphere3
        self.assertAlmostEqual(hit.distance, expected_dist)

        expected_p_near = np.array([0.5, 0.0, 0.0])
        expected_q_near = np.array([0.75, 0.0, 0.0])

        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_a), expected_p_near)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_b), expected_q_near)

    def test_closest_of_box_and_capsule(self):
        # from_size принимает center, size (полный размер)
        box = BoxCollider.from_size(
            Vec3(0.0, 0.0, 0.0),
            Vec3(2.0, 1.0, 0.5)
        )
        capsule = CapsuleCollider(
            Vec3(3.0, 0.0, 0.0),
            Vec3(4.0, 0.0, 0.0),
            0.2
        )

        hit = box.closest_to_collider(capsule)

        expected_distance = 1.8
        self.assertAlmostEqual(hit.distance, expected_distance)

        expected_closest_box_point = np.array([1.0, 0.0, 0.0])
        expected_closest_capsule_point = np.array([2.8, 0.0, 0.0])

        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_a), expected_closest_box_point)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_b), expected_closest_capsule_point)


class AttachedColliderTest(unittest.TestCase):
    def test_attached_collider_distance(self):
        # from_size принимает center, size (полный размер)
        box = BoxCollider.from_size(
            Vec3(0.0, 0.0, 0.0),
            Vec3(2.0, 1.0, 0.5)
        )

        # Проверяем half_size
        np.testing.assert_array_almost_equal(
            vec3_to_np(box.half_size),
            np.array([1.0, 0.5, 0.25])
        )

        trans = GeneralTransform3()
        attached_box = AttachedCollider(box, trans)

        sphere = SphereCollider(Vec3(3.0, 0.0, 0.0), 0.5)
        trans2 = GeneralTransform3()
        attached_sphere = AttachedCollider(sphere, trans2)

        hit = attached_box.closest_to_collider(attached_sphere)

        expected_distance = 1.5  # Distance between surfaces
        expected_p_near = np.array([1.0, 0.0, 0.0])
        expected_q_near = np.array([2.5, 0.0, 0.0])

        self.assertAlmostEqual(hit.distance, expected_distance)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_a), expected_p_near)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_b), expected_q_near)


class TestColliderRay(unittest.TestCase):
    def test_ray_hits_sphere(self):
        sphere = SphereCollider(Vec3(0.0, 0.0, 5.0), 1.0)

        ray = Ray3(Vec3(0.0, 0.0, 0.0), Vec3(0.0, 0.0, 1.0))

        hit = sphere.closest_to_ray(ray)

        # Должно быть прямое попадание — расстояние 0
        self.assertAlmostEqual(hit.distance, 0.0)

        # Точка пересечения должна быть на z = 4 (радиус = 1)
        expected = np.array([0.0, 0.0, 4.0])
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_ray), expected)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_collider), expected)

    def test_ray_misses_sphere(self):
        sphere = SphereCollider(Vec3(0.0, 5.0, 5.0), 1.0)

        ray = Ray3(Vec3(0.0, 0.0, 0.0), Vec3(0.0, 0.0, 1.0))

        hit = sphere.closest_to_ray(ray)

        # Простая геометрия: кратчайшая точка луча — (0,0,5)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_ray), np.array([0.0, 0.0, 5.0]))

        # Точка на сфере ближе всего по вертикали
        # центр = (0,5,5), радиус=1 → ближайшая точка = (0,4,5)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_collider), np.array([0.0, 4.0, 5.0]))

        # Расстояние от луча до центра = 5, до поверхности = 5 - 1 = 4
        self.assertAlmostEqual(hit.distance, 4.0)

    def test_ray_hits_capsule(self):
        capsule = CapsuleCollider(
            Vec3(0.0, 0.0, 3.0),
            Vec3(0.0, 0.0, 7.0),
            1.0
        )

        ray = Ray3(Vec3(0.0, 0.0, 0.0), Vec3(0.0, 0.0, 1.0))

        hit = capsule.closest_to_ray(ray)

        # Луч входит в капсулу на z=2 (нижняя сфера)
        self.assertAlmostEqual(hit.distance, 0.0)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_ray), np.array([0.0, 0.0, 2.0]))
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_collider), np.array([0.0, 0.0, 2.0]))

    def test_ray_misses_capsule(self):
        capsule = CapsuleCollider(
            Vec3(5.0, 0.0, 0.0),
            Vec3(5.0, 0.0, 5.0),
            0.5
        )

        ray = Ray3(Vec3(0.0, 0.0, 0.0), Vec3(0.0, 0.0, 1.0))

        hit = capsule.closest_to_ray(ray)

        # Геометрия:
        # Луч проходит по линии x=0 → кратчайшая точка луча к сегменту — (0,0,z)
        # Ближайшая точка сегмента — (5,0,z)
        # Расстояние = 5 - 0.5 = 4.5
        self.assertAlmostEqual(hit.distance, 4.5)

    def test_ray_hits_box(self):
        box = BoxCollider.from_size(
            Vec3(0.0, 0.0, 5.0),
            Vec3(2.0, 2.0, 2.0)
        )

        ray = Ray3(Vec3(0.0, 0.0, 0.0), Vec3(0.0, 0.0, 1.0))

        hit = box.closest_to_ray(ray)

        # Бокс начинается на z = 4 (size z=2, центр на 5)
        self.assertAlmostEqual(hit.distance, 0.0)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_ray), np.array([0.0, 0.0, 4.0]))

    def test_ray_misses_box(self):
        box = BoxCollider.from_size(
            Vec3(5.0, 0.0, 5.0),
            Vec3(2.0, 2.0, 2.0)
        )

        ray = Ray3(Vec3(0.0, 0.0, 0.0), Vec3(0.0, 0.0, 1.0))

        hit = box.closest_to_ray(ray)

        # Минимальная точка на луче лежит на входной грани z=4 (любая z∈[4,6] эквивалентна)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_ray), np.array([0.0, 0.0, 4.0]))

        # Ближайшая точка в коробке по x — 4 (центр 5, halfsize=1)
        expected_box_pt = np.array([4.0, 0.0, 4.0])
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_collider), expected_box_pt)

        # Расстояние между точками = 4 (смещение только по x)
        self.assertAlmostEqual(hit.distance, 4.0)

    def test_ray_hits_union(self):
        sphere1 = SphereCollider(Vec3(0.0, 0.0, 5.0), 1.0)
        sphere2 = SphereCollider(Vec3(10.0, 0.0, 5.0), 1.0)
        union = UnionCollider([sphere1, sphere2])

        ray = Ray3(Vec3(0.0, 0.0, 0.0), Vec3(0.0, 0.0, 1.0))

        hit = union.closest_to_ray(ray)

        # Попадёт в sphere1
        self.assertAlmostEqual(hit.distance, 0.0)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_ray), np.array([0.0, 0.0, 4.0]))


if __name__ == '__main__':
    unittest.main()
