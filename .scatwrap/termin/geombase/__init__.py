<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/geombase/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
Базовые&nbsp;геометрические&nbsp;классы&nbsp;(Geometric&nbsp;Base).<br>
<br>
Содержит&nbsp;фундаментальные&nbsp;классы&nbsp;для&nbsp;представления&nbsp;геометрии:<br>
-&nbsp;Pose2&nbsp;-&nbsp;позы&nbsp;(положение&nbsp;+&nbsp;ориентация)&nbsp;в&nbsp;2D&nbsp;пространстве<br>
-&nbsp;Pose3&nbsp;-&nbsp;позы&nbsp;(положение&nbsp;+&nbsp;ориентация)&nbsp;в&nbsp;3D&nbsp;пространстве<br>
-&nbsp;Screw,&nbsp;Screw2,&nbsp;Screw3&nbsp;-&nbsp;винтовые&nbsp;преобразования<br>
&quot;&quot;&quot;<br>
<br>
from&nbsp;.pose2&nbsp;import&nbsp;Pose2<br>
from&nbsp;.pose3&nbsp;import&nbsp;Pose3<br>
from&nbsp;.screw&nbsp;import&nbsp;Screw,&nbsp;Screw2,&nbsp;Screw3<br>
from&nbsp;.aabb&nbsp;import&nbsp;AABB,&nbsp;TransformAABB<br>
<br>
__all__&nbsp;=&nbsp;[<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Pose2',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Pose3',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Screw',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Screw2',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Screw3',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'AABB',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'TransformAABB'<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
