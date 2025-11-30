import unittest
import numpy as np

from termin.visualization.core.scene import Scene
from termin.visualization.core.entity import Entity
from termin.colliders.sphere import SphereCollider
from termin.colliders.box import BoxCollider
from termin.colliders.raycast_hit import RaycastHit
from termin.colliders.collider_component import ColliderComponent
from termin.geombase.ray import Ray3


class SceneRaycastTest(unittest.TestCase):

    def make_entity_with_collider(self, collider):
        """
        Создаёт Entity, цепляет ColliderComponent.
        Возвращает entity и компонент.
        """
        e = Entity()
        comp = ColliderComponent(collider)
        e.add_component(comp)
        return e, comp

    def test_raycast_hits_only_intersections(self):
        scene = Scene()

        # Сфера, по которой точно попадёт луч
        sphere_hit = SphereCollider(
            center=np.array([0.0, 0.0, 5.0]),
            radius=1.0
        )
        e1, _ = self.make_entity_with_collider(sphere_hit)
        scene.add(e1)

        # Сфера в стороне — пересечения нет
        sphere_miss = SphereCollider(
            center=np.array([3.0, 0.0, 5.0]),
            radius=1.0
        )
        e2, _ = self.make_entity_with_collider(sphere_miss)
        scene.add(e2)

        ray = Ray3(
            origin=np.array([0.0, 0.0, 0.0]),
            direction=np.array([0.0, 0.0, 1.0])
        )

        hit = scene.raycast(ray)
        self.assertIsNotNone(hit)
        self.assertIs(hit.entity, e1)

        # Точка пересечения
        np.testing.assert_array_almost_equal(hit.point, np.array([0.0, 0.0, 4.0]))
        self.assertAlmostEqual(hit.distance, 0.0)

    def test_closest_to_ray_finds_nearest_even_without_intersection(self):
        scene = Scene()

        # Промах — но ближайшая сфера
        sphere1 = SphereCollider(
            center=np.array([3.0, 0.0, 5.0]),
            radius=1.0
        )
        e1, _ = self.make_entity_with_collider(sphere1)
        scene.add(e1)

        # Далёкая сфера — точно проиграет
        sphere2 = SphereCollider(
            center=np.array([10.0, 0.0, 5.0]),
            radius=1.0
        )
        e2, _ = self.make_entity_with_collider(sphere2)
        scene.add(e2)

        ray = Ray3(
            origin=np.array([0.0, 0.0, 0.0]),
            direction=np.array([0.0, 0.0, 1.0])
        )

        hit = scene.closest_to_ray(ray)
        self.assertIsNotNone(hit)
        self.assertIs(hit.entity, e1)

        # Ближайшая точка на луче должна быть на z = 5
        np.testing.assert_array_almost_equal(hit.point, np.array([0.0, 0.0, 5.0]))

        # Ближайшая точка на сфере — x = 2 (центр 3, радиус 1)
        np.testing.assert_array_almost_equal(hit.collider_point, np.array([2.0, 0.0, 5.0]))

        # Расстояние между точками — 2.0
        self.assertAlmostEqual(hit.distance, 2.0)
