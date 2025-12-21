"""
CapsuleCollider — обёртка над C++ реализацией.
"""

import numpy as np
from termin.geombase import Pose3
from termin.colliders.collider import Collider
from termin.colliders._colliders_native import CapsuleCollider as NativeCapsuleCollider
from termin.geombase._geom_native import Vec3, Pose3 as NativePose3


class CapsuleCollider(Collider):
    """
    Capsule collider — капсула (цилиндр с полусферами на концах).

    Параметры:
        a: Первая точка оси в локальных координатах
        b: Вторая точка оси в локальных координатах
        radius: Радиус
        pose: Поза в мировых координатах
    """

    def __init__(
        self,
        a: np.ndarray = None,
        b: np.ndarray = None,
        radius: float = 0.25,
        pose: Pose3 = None
    ):
        if a is None:
            a = np.array([0, 0, -0.5], dtype=np.float32)
        if b is None:
            b = np.array([0, 0, 0.5], dtype=np.float32)

        self.local_a = np.asarray(a, dtype=np.float32)
        self.local_b = np.asarray(b, dtype=np.float32)
        self.radius = float(radius)
        self.pose = pose if pose is not None else Pose3.identity()

        # Создаём native объект
        self._rebuild_native()

    def _rebuild_native(self):
        """Пересоздать C++ объект из текущих параметров."""
        native_a = Vec3(float(self.local_a[0]), float(self.local_a[1]), float(self.local_a[2]))
        native_b = Vec3(float(self.local_b[0]), float(self.local_b[1]), float(self.local_b[2]))

        # Конвертируем Pose3
        if hasattr(self.pose, 'lin') and hasattr(self.pose, 'ang'):
            native_pose = NativePose3(
                Vec3(float(self.pose.lin[0]), float(self.pose.lin[1]), float(self.pose.lin[2])),
                self.pose.ang  # Quat уже native
            )
        else:
            native_pose = NativePose3()

        self._native = NativeCapsuleCollider(native_a, native_b, self.radius, native_pose)

    def transform_by(self, tpose: Pose3) -> "CapsuleCollider":
        """Return a new CapsuleCollider transformed by the given Pose3."""
        new_pose = tpose * self.pose
        return CapsuleCollider(self.local_a.copy(), self.local_b.copy(), self.radius, new_pose)

    def scale_by(self, scale: np.ndarray) -> "CapsuleCollider":
        """Return a new CapsuleCollider with scaled size."""
        scale_arr = np.asarray(scale, dtype=np.float32)
        new_a = self.local_a * scale_arr
        new_b = self.local_b * scale_arr
        # Radius scales uniformly (average)
        new_radius = self.radius * float(np.mean(scale_arr))
        return CapsuleCollider(new_a, new_b, new_radius, self.pose)

    def __repr__(self):
        return f"CapsuleCollider(a={self.local_a}, b={self.local_b}, radius={self.radius}, pose={self.pose})"

    # Свойства для совместимости со старым кодом
    @property
    def a(self) -> np.ndarray:
        """Первая точка оси в мировых координатах."""
        native_a = self._native.world_a()
        return np.array([native_a.x, native_a.y, native_a.z], dtype=np.float32)

    @property
    def b(self) -> np.ndarray:
        """Вторая точка оси в мировых координатах."""
        native_b = self._native.world_b()
        return np.array([native_b.x, native_b.y, native_b.z], dtype=np.float32)
