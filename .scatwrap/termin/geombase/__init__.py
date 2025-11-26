<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/geombase/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
Базовые геометрические классы (Geometric Base).<br>
<br>
Содержит фундаментальные классы для представления геометрии:<br>
- Pose2 - позы (положение + ориентация) в 2D пространстве<br>
- Pose3 - позы (положение + ориентация) в 3D пространстве<br>
- Screw, Screw2, Screw3 - винтовые преобразования<br>
&quot;&quot;&quot;<br>
<br>
from .pose2 import Pose2<br>
from .pose3 import Pose3<br>
from .screw import Screw, Screw2, Screw3<br>
from .aabb import AABB, TransformAABB<br>
<br>
__all__ = [<br>
&#9;'Pose2',<br>
&#9;'Pose3',<br>
&#9;'Screw',<br>
&#9;'Screw2',<br>
&#9;'Screw3',<br>
&#9;'AABB',<br>
&#9;'TransformAABB'<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
