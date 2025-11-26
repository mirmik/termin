<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/kinematic/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
Модуль кинематики и трансформаций.<br>
<br>
Содержит классы для работы с:<br>
- Трансформациями (Transform, Transform3)<br>
- Кинематическими преобразованиями (Rotator3, Actuator3)<br>
- Кинематическими цепями (KinematicChain3)<br>
&quot;&quot;&quot;<br>
<br>
from .transform import Transform, Transform3<br>
from .kinematic import (<br>
&#9;KinematicTransform3,<br>
&#9;KinematicTransform3OneScrew,<br>
&#9;Rotator3,<br>
&#9;Actuator3<br>
)<br>
from .kinchain import KinematicChain3<br>
from .conditions import SymCondition, ConditionCollection<br>
<br>
__all__ = [<br>
&#9;'Transform',<br>
&#9;'Transform3',<br>
&#9;'KinematicTransform3',<br>
&#9;'KinematicTransform3OneScrew',<br>
&#9;'Rotator3',<br>
&#9;'Actuator3',<br>
&#9;'KinematicChain3',<br>
&#9;'SymCondition',<br>
&#9;'ConditionCollection'<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
