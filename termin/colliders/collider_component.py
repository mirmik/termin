from __future__ import annotations

from typing import TYPE_CHECKING

from termin.colliders.attached import AttachedCollider
from termin.colliders.collider import Collider

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene


def _get_component_base():
    from termin.visualization.core.entity import Component
    return Component


class ColliderComponent(_get_component_base()):
    """
    Компонент, навешиваемый на Entity.
    Оборачивает коллайдер в AttachedCollider, чтобы он следовал за Transform3.
    """

    def __init__(self, collider: Collider | None = None):
        super().__init__(enabled=True)
        if collider is None:
            from termin.colliders.box import BoxCollider
            collider = BoxCollider()
        self._source_collider = collider
        self.attached = None

    def on_added(self, scene):
        super().on_added(scene)
        if self.entity is None:
            return
        # entity.transform всегда Transform3
        self.attached = AttachedCollider(self._source_collider, self.entity.transform)

    def get_collider(self):
        return self.attached
