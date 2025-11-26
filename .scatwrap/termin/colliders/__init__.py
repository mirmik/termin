<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
Модуль коллайдеров для обнаружения столкновений и вычисления расстояний.<br>
<br>
Содержит:<br>
- Базовый класс Collider<br>
- Примитивные коллайдеры: Sphere, Box, Capsule<br>
- AttachedCollider - коллайдер, прикрепленный к трансформации<br>
- UnionCollider - объединение нескольких коллайдеров<br>
&quot;&quot;&quot;<br>
<br>
from .collider import Collider<br>
from .sphere import SphereCollider<br>
from .box import BoxCollider<br>
from .capsule import CapsuleCollider<br>
from .attached import AttachedCollider<br>
from .union_collider import UnionCollider<br>
<br>
__all__ = [<br>
    'Collider',<br>
    'SphereCollider',<br>
    'BoxCollider',<br>
    'CapsuleCollider',<br>
    'AttachedCollider',<br>
    'UnionCollider',<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
