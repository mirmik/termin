<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
Termin - библиотека для кинематики, динамики и мультифизического моделирования.<br>
<br>
Основные модули:<br>
- geombase - базовые геометрические классы (Pose3, Screw2, Screw3)<br>
- kinematics - трансформации и кинематические цепи<br>
- fem - метод конечных элементов для мультифизики<br>
&quot;&quot;&quot;<br>
<br>
# Базовая геометрия<br>
from .geombase import Pose3, Screw2, Screw3<br>
<br>
__version__ = '0.1.0'<br>
<br>
__all__ = [<br>
&#9;# Geombase<br>
&#9;'Pose3',<br>
&#9;'Screw2',<br>
&#9;'Screw3',<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
