"""
SphereCollider — обёртка над C++ реализацией.
"""

import numpy as np
from termin.geombase import Pose3
from termin.colliders.collider import Collider
from termin.colliders._colliders_native import SphereCollider as NativeSphereCollider
from termin.geombase._geom_native import Vec3, Pose3 as NativePose3


class SphereCollider(Collider):
    """
    Sphere collider — сфера.

    Параметры:
        center: Центр в локальных координатах
        radius: Радиус
        pose: Поза в мировых координатах
    """

    def __init__(
        self,
        center: np.ndarray = None,
        radius: float = 0.5,
        pose: Pose3 = None
    ):
        if center is None:
            center = np.zeros(3, dtype=np.float32)

        self.center_local = np.asarray(center, dtype=np.float32)
        self.radius = float(radius)
        self.pose = pose if pose is not None else Pose3.identity()

        # Создаём native объект
        self._rebuild_native()

    def _rebuild_native(self):
        """Пересоздать C++ объект из текущих параметров."""
        native_center = Vec3(float(self.center_local[0]), float(self.center_local[1]), float(self.center_local[2]))

        # Конвертируем Pose3
        if hasattr(self.pose, 'lin') and hasattr(self.pose, 'ang'):
            native_pose = NativePose3(
                Vec3(float(self.pose.lin[0]), float(self.pose.lin[1]), float(self.pose.lin[2])),
                self.pose.ang  # Quat уже native
            )
        else:
            native_pose = NativePose3()

        self._native = NativeSphereCollider(native_center, self.radius, native_pose)

    def transform_by(self, tpose: Pose3) -> "SphereCollider":
        """Return a new SphereCollider transformed by the given Pose3."""
        new_pose = tpose * self.pose
        return SphereCollider(self.center_local.copy(), self.radius, new_pose)

    def scale_by(self, scale: float) -> "SphereCollider":
        """Return a new SphereCollider with scaled radius."""
        # For sphere, we use uniform scale (average if array)
        if hasattr(scale, '__len__'):
            scale = float(np.mean(scale))
        new_radius = self.radius * scale
        new_center = self.center_local * scale
        return SphereCollider(new_center, new_radius, self.pose)

    def __repr__(self):
        return f"SphereCollider(center={self.center_local}, radius={self.radius}, pose={self.pose})"

    # Свойства для совместимости со старым кодом
    @property
    def center(self) -> np.ndarray:
        """Центр в мировых координатах."""
        return Collider.center(self)
