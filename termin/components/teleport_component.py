"""TeleportComponent — телепортирует entity в точку клика по коллайдеру."""

from __future__ import annotations

from termin.visualization.core.component import InputComponent
from termin.visualization.core.input_events import MouseButtonEvent
from tcbase import MouseButton, Action


class TeleportComponent(InputComponent):
    """
    Компонент телепортации.

    При клике ЛКМ делает рейкаст и телепортирует entity
    в точку пересечения с коллайдером.
    """

    def on_mouse_button(self, event: MouseButtonEvent):
        # Только при нажатии ЛКМ
        if event.button != MouseButton.LEFT or event.action != Action.PRESS:
            return

        if self.entity is None:
            return

        # Получаем луч из позиции курсора
        ray = event.viewport.screen_point_to_ray(event.x, event.y)
        if ray is None:
            return

        # Рейкаст по сцене
        scene = event.viewport.scene
        hit = scene.raycast(ray)
        if hit is None:
            return

        # Не телепортируемся в себя
        if hit.entity is self.entity:
            return

        # Телепортируем в точку пересечения
        from termin.geombase import Pose3

        old_pose = self.entity.transform.global_pose()
        new_pose = Pose3(lin=hit.collider_point, ang=old_pose.ang)
        self.entity.transform.relocate_global(new_pose)
