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
    KinematicTransform3,<br>
    KinematicTransform3OneScrew,<br>
    Rotator3,<br>
    Actuator3<br>
)<br>
from .kinchain import KinematicChain3<br>
from .conditions import SymCondition, ConditionCollection<br>
<br>
__all__ = [<br>
    'Transform',<br>
    'Transform3',<br>
    'KinematicTransform3',<br>
    'KinematicTransform3OneScrew',<br>
    'Rotator3',<br>
    'Actuator3',<br>
    'KinematicChain3',<br>
    'SymCondition',<br>
    'ConditionCollection'<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
