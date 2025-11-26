<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/__init__.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;
Termin - библиотека для кинематики, динамики и мультифизического моделирования.

Основные модули:
- geombase - базовые геометрические классы (Pose3, Screw2, Screw3)
- kinematics - трансформации и кинематические цепи
- fem - метод конечных элементов для мультифизики
&quot;&quot;&quot;

# Базовая геометрия
from .geombase import Pose3, Screw2, Screw3

__version__ = '0.1.0'

__all__ = [
    # Geombase
    'Pose3',
    'Screw2',
    'Screw3',
]

</code></pre>
</body>
</html>
