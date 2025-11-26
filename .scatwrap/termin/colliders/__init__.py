<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/__init__.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;
Модуль коллайдеров для обнаружения столкновений и вычисления расстояний.

Содержит:
- Базовый класс Collider
- Примитивные коллайдеры: Sphere, Box, Capsule
- AttachedCollider - коллайдер, прикрепленный к трансформации
- UnionCollider - объединение нескольких коллайдеров
&quot;&quot;&quot;

from .collider import Collider
from .sphere import SphereCollider
from .box import BoxCollider
from .capsule import CapsuleCollider
from .attached import AttachedCollider
from .union_collider import UnionCollider

__all__ = [
    'Collider',
    'SphereCollider',
    'BoxCollider',
    'CapsuleCollider',
    'AttachedCollider',
    'UnionCollider',
]

</code></pre>
</body>
</html>
