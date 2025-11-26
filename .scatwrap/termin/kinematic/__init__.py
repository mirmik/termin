<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/kinematic/__init__.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;
Модуль кинематики и трансформаций.

Содержит классы для работы с:
- Трансформациями (Transform, Transform3)
- Кинематическими преобразованиями (Rotator3, Actuator3)
- Кинематическими цепями (KinematicChain3)
&quot;&quot;&quot;

from .transform import Transform, Transform3
from .kinematic import (
    KinematicTransform3,
    KinematicTransform3OneScrew,
    Rotator3,
    Actuator3
)
from .kinchain import KinematicChain3
from .conditions import SymCondition, ConditionCollection

__all__ = [
    'Transform',
    'Transform3',
    'KinematicTransform3',
    'KinematicTransform3OneScrew',
    'Rotator3',
    'Actuator3',
    'KinematicChain3',
    'SymCondition',
    'ConditionCollection'
]

</code></pre>
</body>
</html>
