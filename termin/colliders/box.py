"""
BoxCollider — обёртка над C++ реализацией.
"""

import numpy as np
from termin.geombase import Pose3
from termin.colliders.collider import Collider
from termin.colliders._colliders_native import BoxCollider as NativeBoxCollider
from termin.geombase._geom_native import Vec3, Pose3 as NativePose3


class BoxCollider(Collider):
    """
    Box collider — ориентированный параллелепипед.

    Параметры:
        center: Центр в локальных координатах
        size: Полный размер (не half_size)
        pose: Поза в мировых координатах
    """

    def __init__(
        self,
        center: np.ndarray = None,
        size: np.ndarray = None,
        pose: Pose3 = None
    ):
        if center is None:
            center = np.zeros(3, dtype=np.float32)
        if size is None:
            size = np.ones(3, dtype=np.float32)

        self.center_local = np.asarray(center, dtype=np.float32)
        self.size = np.asarray(size, dtype=np.float32)
        self.pose = pose if pose is not None else Pose3.identity()

        # Создаём native объект
        self._rebuild_native()

    def _rebuild_native(self):
        """Пересоздать C++ объект из текущих параметров."""
        native_center = Vec3(float(self.center_local[0]), float(self.center_local[1]), float(self.center_local[2]))
        half_size = self.size / 2.0
        native_half = Vec3(float(half_size[0]), float(half_size[1]), float(half_size[2]))

        # Конвертируем Pose3
        if hasattr(self.pose, 'lin') and hasattr(self.pose, 'ang'):
            native_pose = NativePose3(
                Vec3(float(self.pose.lin[0]), float(self.pose.lin[1]), float(self.pose.lin[2])),
                self.pose.ang  # Quat уже native
            )
        else:
            native_pose = NativePose3()

        self._native = NativeBoxCollider(native_center, native_half, native_pose)

    def transform_by(self, tpose: Pose3) -> "BoxCollider":
        """Return a new BoxCollider transformed by the given Pose3."""
        new_pose = tpose * self.pose
        return BoxCollider(self.center_local.copy(), self.size.copy(), new_pose)

    def scale_by(self, scale: np.ndarray) -> "BoxCollider":
        """Return a new BoxCollider with scaled size."""
        new_size = self.size * np.asarray(scale, dtype=np.float32)
        new_center = self.center_local * np.asarray(scale, dtype=np.float32)
        return BoxCollider(new_center, new_size, self.pose)

    def local_aabb(self):
        """AABB в локальных координатах."""
        from termin.geombase import AABB
        half_size = self.size / 2.0
        min_point = self.center_local - half_size
        max_point = self.center_local + half_size
        return AABB(min_point, max_point)

    def __repr__(self):
        return f"BoxCollider(center={self.center_local}, size={self.size}, pose={self.pose})"

    # Свойства для совместимости со старым кодом
    @property
    def center(self) -> np.ndarray:
        """Центр в локальных координатах (для совместимости)."""
        return self.center_local
