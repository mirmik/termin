<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/geombase/__init__.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;
Базовые геометрические классы (Geometric Base).

Содержит фундаментальные классы для представления геометрии:
- Pose2 - позы (положение + ориентация) в 2D пространстве
- Pose3 - позы (положение + ориентация) в 3D пространстве
- Screw, Screw2, Screw3 - винтовые преобразования
&quot;&quot;&quot;

from .pose2 import Pose2
from .pose3 import Pose3
from .screw import Screw, Screw2, Screw3
from .aabb import AABB, TransformAABB

__all__ = [
    'Pose2',
    'Pose3',
    'Screw',
    'Screw2',
    'Screw3',
    'AABB',
    'TransformAABB'
]

</code></pre>
</body>
</html>
