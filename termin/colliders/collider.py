"""
Базовый класс коллайдера — обёртка над C++ реализацией.
"""

import numpy as np
from termin.colliders._colliders_native import (
    Collider as NativeCollider,
    RayHit,
    ColliderHit,
)


class Collider:
    """
    Базовый класс для Python-обёрток над C++ коллайдерами.

    Подклассы должны определить self._native с ссылкой на C++ объект.
    """

    _native: NativeCollider

    def closest_to_ray(self, ray: "Ray3"):
        """
        Возвращает (p_col, p_ray, distance) — ближайшие точки между коллайдером и лучом.
        """
        from termin.colliders._colliders_native import Ray3 as NativeRay3
        from termin.geombase._geom_native import Vec3

        # Конвертируем Ray3 если нужно
        if hasattr(ray, 'origin') and hasattr(ray, 'direction'):
            native_ray = NativeRay3(
                Vec3(float(ray.origin[0]), float(ray.origin[1]), float(ray.origin[2])),
                Vec3(float(ray.direction[0]), float(ray.direction[1]), float(ray.direction[2]))
            )
        else:
            native_ray = ray

        hit = self._native.closest_to_ray(native_ray)

        p_col = np.array([hit.point_on_collider.x, hit.point_on_collider.y, hit.point_on_collider.z], dtype=np.float32)
        p_ray = np.array([hit.point_on_ray.x, hit.point_on_ray.y, hit.point_on_ray.z], dtype=np.float32)

        return p_col, p_ray, hit.distance

    def transform_by(self, transform: 'Pose3') -> "Collider":
        """Return a new Collider transformed by the given Pose3."""
        raise NotImplementedError("transform_by must be implemented by subclasses.")

    def closest_to_collider(self, other: "Collider"):
        """
        Возвращает (p_a, p_b, distance) — ближайшие точки между коллайдерами.
        """
        # Получаем native объект другого коллайдера
        other_native = other._native if hasattr(other, '_native') else other

        hit = self._native.closest_to_collider(other_native)

        p_a = np.array([hit.point_on_a.x, hit.point_on_a.y, hit.point_on_a.z], dtype=np.float32)
        p_b = np.array([hit.point_on_b.x, hit.point_on_b.y, hit.point_on_b.z], dtype=np.float32)

        return p_a, p_b, hit.distance

    def avoidance(self, other: "Collider") -> tuple:
        """Compute an avoidance vector to maintain a minimum distance from another collider."""
        p_near, q_near, dist = self.closest_to_collider(other)
        diff = p_near - q_near
        real_dist = np.linalg.norm(diff)
        if real_dist < 1e-10:
            return np.zeros(3), 0.0, p_near
        direction = diff / real_dist
        return direction, real_dist, p_near

    def center(self) -> np.ndarray:
        """Центр коллайдера в мировых координатах."""
        c = self._native.center()
        return np.array([c.x, c.y, c.z], dtype=np.float32)
