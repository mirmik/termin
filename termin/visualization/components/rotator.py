"""Simple rotation component for testing game mode."""

from __future__ import annotations

import numpy as np
from termin.visualization.core.python_component import PythonComponent
from termin.editor.inspect_field import inspect
from termin.geombase import Pose3
from termin.util import qmul


class RotatorComponent(PythonComponent):
    """Компонент, который вращает entity вокруг заданной оси."""

    speed = inspect(
        90.0, label="Speed (deg/s)", kind="float",
        min=-360.0, max=360.0, step=1.0,
    )

    axis = inspect(
        np.array([0.0, 0.0, 1.0], dtype=np.float32),
        label="Axis", kind="vec3",
    )

    serializable_fields = ["speed", "axis"]

    def __init__(
        self,
        speed: float = 90.0,
        axis: np.ndarray | list | None = None,
    ):
        super().__init__(enabled=True)
        self.speed = speed  # градусов в секунду
        if axis is None:
            axis = [0.0, 0.0, 1.0]
        self.axis = np.array(axis, dtype=np.float32)
        # Нормализуем ось
        norm = np.linalg.norm(self.axis)
        if norm > 0:
            self.axis = self.axis / norm

    def update(self, dt: float):
        if self.entity is None:
            return

        # Угол поворота за этот кадр (в радианах)
        angle_rad = np.radians(self.speed * dt)

        # Создаём инкрементальный поворот
        delta_rotation = Pose3.rotation(self.axis, angle_rad)

        # Получаем текущую позу
        current_pose = self.entity.transform.local_pose()

        # Применяем поворот: new_q = current_q * delta_q
        new_ang = qmul(current_pose.ang, delta_rotation.ang)

        # Обновляем позу
        new_pose = Pose3(lin=current_pose.lin, ang=new_ang)
        self.entity.transform.relocate(new_pose)
