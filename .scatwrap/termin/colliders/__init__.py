<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
Модуль&nbsp;коллайдеров&nbsp;для&nbsp;обнаружения&nbsp;столкновений&nbsp;и&nbsp;вычисления&nbsp;расстояний.<br>
<br>
Содержит:<br>
-&nbsp;Базовый&nbsp;класс&nbsp;Collider<br>
-&nbsp;Примитивные&nbsp;коллайдеры:&nbsp;Sphere,&nbsp;Box,&nbsp;Capsule<br>
-&nbsp;AttachedCollider&nbsp;-&nbsp;коллайдер,&nbsp;прикрепленный&nbsp;к&nbsp;трансформации<br>
-&nbsp;UnionCollider&nbsp;-&nbsp;объединение&nbsp;нескольких&nbsp;коллайдеров<br>
&quot;&quot;&quot;<br>
<br>
from&nbsp;.collider&nbsp;import&nbsp;Collider<br>
from&nbsp;.sphere&nbsp;import&nbsp;SphereCollider<br>
from&nbsp;.box&nbsp;import&nbsp;BoxCollider<br>
from&nbsp;.capsule&nbsp;import&nbsp;CapsuleCollider<br>
from&nbsp;.attached&nbsp;import&nbsp;AttachedCollider<br>
from&nbsp;.union_collider&nbsp;import&nbsp;UnionCollider<br>
<br>
__all__&nbsp;=&nbsp;[<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Collider',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'SphereCollider',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'BoxCollider',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'CapsuleCollider',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'AttachedCollider',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'UnionCollider',<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
