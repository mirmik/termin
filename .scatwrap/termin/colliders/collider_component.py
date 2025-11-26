<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/collider_component.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from&nbsp;termin.colliders.attached&nbsp;import&nbsp;AttachedCollider<br>
from&nbsp;termin.colliders.collider&nbsp;import&nbsp;Collider<br>
from&nbsp;termin.visualization.entity&nbsp;import&nbsp;Component&nbsp;<br>
<br>
class&nbsp;ColliderComponent(Component):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Компонент,&nbsp;навешиваемый&nbsp;на&nbsp;Entity.<br>
&nbsp;&nbsp;&nbsp;&nbsp;Оборачивает&nbsp;коллайдер&nbsp;в&nbsp;AttachedCollider,&nbsp;чтобы&nbsp;он&nbsp;следовал&nbsp;за&nbsp;Transform3.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;collider:&nbsp;Collider):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().__init__(enabled=True)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self._source_collider&nbsp;=&nbsp;collider<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.attached&nbsp;=&nbsp;None<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;start(self,&nbsp;scene):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;super().start(scene)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;self.entity&nbsp;is&nbsp;None:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;entity.transform&nbsp;всегда&nbsp;Transform3<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.attached&nbsp;=&nbsp;AttachedCollider(self._source_collider,&nbsp;self.entity.transform)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;get_collider(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.attached<br>
<!-- END SCAT CODE -->
</body>
</html>
