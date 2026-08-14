import unittest
import numpy as np
from termin.colliders import (
    CapsuleCollider, SphereCollider, BoxCollider,
    UnionCollider, AttachedCollider, Ray3
)
from termin.geombase import GeneralPose3, Quat
from termin.geombase._geom_native import Vec3
from termin.scene import GeneralTransform3


def vec3_to_np(v: Vec3) -> np.ndarray:
    return np.array([v.x, v.y, v.z])


class TestCollider(unittest.TestCase):
    def test_closest_to_capsule(self):
        capsule1 = CapsuleCollider(0.5, 0.25)  # from (0,0,-0.5) to (0,0,0.5)

        capsule2 = CapsuleCollider(0.0, 0.25, GeneralPose3(Quat.identity(), Vec3(1.0, 0.0, 0.0)))

        hit = capsule1.closest_to_collider(capsule2)

        expected_dist = 0.5
        self.assertAlmostEqual(hit.distance, expected_dist)

        expected_p_near = np.array([0.25, 0.0, 0.0])
        expected_q_near = np.array([0.75, 0.0, 0.0])

        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_a), expected_p_near)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_b), expected_q_near)

    def test_closest_sphere_to_capsule(self):
        capsule = CapsuleCollider(1.0, 0.5)

        sphere = SphereCollider(0.5, GeneralPose3(Quat.identity(), Vec3(1.0, 0.0, 1.0)))

        hit = sphere.closest_to_collider(capsule)

        expected_dist = 0.0  # They are touching
        self.assertAlmostEqual(hit.distance, expected_dist)

        expected_p_near = np.array([0.5, 0.0, 1.0])
        expected_q_near = np.array([0.5, 0.0, 1.0])

        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_a), expected_p_near)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_b), expected_q_near)

    def test_closest_union_collider(self):
        sphere1 = SphereCollider(0.5)  # at origin
        sphere2 = SphereCollider(0.5, GeneralPose3(Quat.identity(), Vec3(3.0, 0.0, 0.0)))
        union_collider = UnionCollider([sphere1, sphere2])

        test_sphere = SphereCollider(0.5, GeneralPose3(Quat.identity(), Vec3(0.0, 1.5, 0.0)))

        hit = union_collider.closest_to_collider(test_sphere)

        expected_dist = 0.5  # Closest to sphere1
        self.assertAlmostEqual(hit.distance, expected_dist)

        expected_p_near = np.array([0.0, 0.5, 0.0])
        expected_q_near = np.array([0.0, 1.0, 0.0])

        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_a), expected_p_near)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_b), expected_q_near)

    def test_two_union_colliders(self):
        sphere1 = SphereCollider(0.5)  # at origin
        sphere2 = SphereCollider(0.5, GeneralPose3(Quat.identity(), Vec3(3.0, 0.0, 0.0)))
        union_collider1 = UnionCollider([sphere1, sphere2])

        sphere3 = SphereCollider(0.5, GeneralPose3(Quat.identity(), Vec3(1.25, 0.0, 0.0)))
        sphere4 = SphereCollider(0.5, GeneralPose3(Quat.identity(), Vec3(5.0, 0.0, 0.0)))
        union_collider2 = UnionCollider([sphere3, sphere4])

        hit = union_collider1.closest_to_collider(union_collider2)

        expected_dist = 0.25  # Closest between sphere1 and sphere3
        self.assertAlmostEqual(hit.distance, expected_dist)

        expected_p_near = np.array([0.5, 0.0, 0.0])
        expected_q_near = np.array([0.75, 0.0, 0.0])

        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_a), expected_p_near)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_b), expected_q_near)

    def test_closest_of_box_and_capsule(self):
        box = BoxCollider.from_size(Vec3(2.0, 1.0, 0.5))

        # For X-axis capsule: rotate around Y by 90 degrees
        rot_y_90 = Quat.from_axis_angle(Vec3(0, 1, 0), np.pi/2)
        capsule = CapsuleCollider(0.5, 0.2, GeneralPose3(rot_y_90, Vec3(3.5, 0.0, 0.0)))

        hit = box.closest_to_collider(capsule)

        expected_distance = 1.8
        self.assertAlmostEqual(hit.distance, expected_distance)

        expected_closest_box_point = np.array([1.0, 0.0, 0.0])
        expected_closest_capsule_point = np.array([2.8, 0.0, 0.0])

        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_a), expected_closest_box_point)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_b), expected_closest_capsule_point)


class AttachedColliderTest(unittest.TestCase):
    def test_attached_collider_distance(self):
        box = BoxCollider.from_size(Vec3(2.0, 1.0, 0.5))

        # Check half_size
        np.testing.assert_array_almost_equal(
            vec3_to_np(box.half_size),
            np.array([1.0, 0.5, 0.25])
        )

        trans = GeneralTransform3()
        attached_box = AttachedCollider(box, trans)

        sphere = SphereCollider(0.5, GeneralPose3(Quat.identity(), Vec3(3.0, 0.0, 0.0)))
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
        sphere = SphereCollider(1.0, GeneralPose3(Quat.identity(), Vec3(0.0, 0.0, 5.0)))

        ray = Ray3(Vec3(0.0, 0.0, 0.0), Vec3(0.0, 0.0, 1.0))

        hit = sphere.closest_to_ray(ray)

        # Hit distance should be 0
        self.assertAlmostEqual(hit.distance, 0.0)

        # Hit point should be at z = 4 (radius = 1)
        expected = np.array([0.0, 0.0, 4.0])
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_ray), expected)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_collider), expected)

    def test_ray_misses_sphere(self):
        sphere = SphereCollider(1.0, GeneralPose3(Quat.identity(), Vec3(0.0, 5.0, 5.0)))

        ray = Ray3(Vec3(0.0, 0.0, 0.0), Vec3(0.0, 0.0, 1.0))

        hit = sphere.closest_to_ray(ray)

        # Closest point on ray is (0,0,5)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_ray), np.array([0.0, 0.0, 5.0]))

        # Closest point on sphere is (0,4,5) - towards the ray
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_collider), np.array([0.0, 4.0, 5.0]))

        # Distance = 5 - 1 = 4
        self.assertAlmostEqual(hit.distance, 4.0)

    def test_ray_hits_capsule(self):
        capsule = CapsuleCollider(2.0, 1.0, GeneralPose3(Quat.identity(), Vec3(0.0, 0.0, 5.0)))

        ray = Ray3(Vec3(0.0, 0.0, 0.0), Vec3(0.0, 0.0, 1.0))

        hit = capsule.closest_to_ray(ray)

        # Ray enters capsule at z=2 (bottom cap at z=3-1=2)
        self.assertAlmostEqual(hit.distance, 0.0)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_ray), np.array([0.0, 0.0, 2.0]))
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_collider), np.array([0.0, 0.0, 2.0]))

    def test_ray_misses_capsule(self):
        capsule = CapsuleCollider(2.5, 0.5, GeneralPose3(Quat.identity(), Vec3(5.0, 0.0, 2.5)))

        ray = Ray3(Vec3(0.0, 0.0, 0.0), Vec3(0.0, 0.0, 1.0))

        hit = capsule.closest_to_ray(ray)

        # Distance = 5 - 0.5 = 4.5
        self.assertAlmostEqual(hit.distance, 4.5)

    def test_ray_hits_box(self):
        box = BoxCollider.from_size(
            Vec3(2.0, 2.0, 2.0),
            GeneralPose3(Quat.identity(), Vec3(0.0, 0.0, 5.0))
        )

        ray = Ray3(Vec3(0.0, 0.0, 0.0), Vec3(0.0, 0.0, 1.0))

        hit = box.closest_to_ray(ray)

        # Box starts at z = 4 (size z=2, center on 5)
        self.assertAlmostEqual(hit.distance, 0.0)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_ray), np.array([0.0, 0.0, 4.0]))

    def test_ray_misses_box(self):
        box = BoxCollider.from_size(
            Vec3(2.0, 2.0, 2.0),
            GeneralPose3(Quat.identity(), Vec3(5.0, 0.0, 5.0))
        )

        ray = Ray3(Vec3(0.0, 0.0, 0.0), Vec3(0.0, 0.0, 1.0))

        hit = box.closest_to_ray(ray)

        # Closest point on ray is at z=4 (box face)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_ray), np.array([0.0, 0.0, 4.0]))

        # Closest point on box is at x=4 (center 5, halfsize=1)
        expected_box_pt = np.array([4.0, 0.0, 4.0])
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_collider), expected_box_pt)

        # Distance = 4 (x offset only)
        self.assertAlmostEqual(hit.distance, 4.0)

    def test_ray_hits_union(self):
        sphere1 = SphereCollider(1.0, GeneralPose3(Quat.identity(), Vec3(0.0, 0.0, 5.0)))
        sphere2 = SphereCollider(1.0, GeneralPose3(Quat.identity(), Vec3(10.0, 0.0, 5.0)))
        union = UnionCollider([sphere1, sphere2])

        ray = Ray3(Vec3(0.0, 0.0, 0.0), Vec3(0.0, 0.0, 1.0))

        hit = union.closest_to_ray(ray)

        # Will hit sphere1
        self.assertAlmostEqual(hit.distance, 0.0)
        np.testing.assert_array_almost_equal(vec3_to_np(hit.point_on_ray), np.array([0.0, 0.0, 4.0]))
