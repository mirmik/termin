from termin.colliders.attached import AttachedCollider
from termin.colliders.collider import Collider
from termin.visualization.core.entity import Component 

class ColliderComponent(Component):
    """
    Компонент, навешиваемый на Entity.
    Оборачивает коллайдер в AttachedCollider, чтобы он следовал за Transform3.
    """
    def __init__(self, collider: Collider):
        super().__init__(enabled=True)
        self._source_collider = collider
        self.attached = None

    def start(self, scene):
        super().start(scene)
        if self.entity is None:
            return
        # entity.transform всегда Transform3
        self.attached = AttachedCollider(self._source_collider, self.entity.transform)

    def get_collider(self):
        return self.attached
