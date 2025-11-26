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
&#9;&quot;&quot;&quot;<br>
&#9;Компонент, навешиваемый на Entity.<br>
&#9;Оборачивает коллайдер в AttachedCollider, чтобы он следовал за Transform3.<br>
&#9;&quot;&quot;&quot;<br>
&#9;def __init__(self, collider: Collider):<br>
&#9;&#9;super().__init__(enabled=True)<br>
&#9;&#9;self._source_collider = collider<br>
&#9;&#9;self.attached = None<br>
<br>
&#9;def start(self, scene):<br>
&#9;&#9;super().start(scene)<br>
&#9;&#9;if self.entity is None:<br>
&#9;&#9;&#9;return<br>
&#9;&#9;# entity.transform всегда Transform3<br>
&#9;&#9;self.attached = AttachedCollider(self._source_collider, self.entity.transform)<br>
<br>
&#9;def get_collider(self):<br>
&#9;&#9;return self.attached<br>
<!-- END SCAT CODE -->
</body>
</html>
