<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/collider_component.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from termin.colliders.attached import AttachedCollider<br>
from termin.colliders.collider import Collider<br>
from termin.visualization.entity import Component <br>
<br>
class ColliderComponent(Component):<br>
    &quot;&quot;&quot;<br>
    Компонент, навешиваемый на Entity.<br>
    Оборачивает коллайдер в AttachedCollider, чтобы он следовал за Transform3.<br>
    &quot;&quot;&quot;<br>
    def __init__(self, collider: Collider):<br>
        super().__init__(enabled=True)<br>
        self._source_collider = collider<br>
        self.attached = None<br>
<br>
    def start(self, scene):<br>
        super().start(scene)<br>
        if self.entity is None:<br>
            return<br>
        # entity.transform всегда Transform3<br>
        self.attached = AttachedCollider(self._source_collider, self.entity.transform)<br>
<br>
    def get_collider(self):<br>
        return self.attached<br>
<!-- END SCAT CODE -->
</body>
</html>
