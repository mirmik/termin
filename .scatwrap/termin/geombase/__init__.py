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
-&nbsp;GeneralPose3&nbsp;-&nbsp;позы&nbsp;с&nbsp;масштабированием<br>
-&nbsp;Screw,&nbsp;Screw2,&nbsp;Screw3&nbsp;-&nbsp;винтовые&nbsp;преобразования<br>
<br>
Использует&nbsp;скомпилированный&nbsp;C++&nbsp;модуль&nbsp;для&nbsp;Pose3,&nbsp;GeneralPose3&nbsp;и&nbsp;связанных&nbsp;типов.<br>
&quot;&quot;&quot;<br>
<br>
#&nbsp;Setup&nbsp;DLL&nbsp;paths&nbsp;before&nbsp;importing&nbsp;native&nbsp;extensions<br>
from&nbsp;termin&nbsp;import&nbsp;_dll_setup&nbsp;&nbsp;#&nbsp;noqa:&nbsp;F401<br>
<br>
#&nbsp;Import&nbsp;C++&nbsp;native&nbsp;implementations<br>
from&nbsp;._geom_native&nbsp;import&nbsp;(<br>
&nbsp;&nbsp;&nbsp;&nbsp;Vec3,<br>
&nbsp;&nbsp;&nbsp;&nbsp;Vec4,<br>
&nbsp;&nbsp;&nbsp;&nbsp;Quat,<br>
&nbsp;&nbsp;&nbsp;&nbsp;Mat44,<br>
&nbsp;&nbsp;&nbsp;&nbsp;Mat44f,<br>
&nbsp;&nbsp;&nbsp;&nbsp;Pose3,<br>
&nbsp;&nbsp;&nbsp;&nbsp;GeneralPose3,<br>
&nbsp;&nbsp;&nbsp;&nbsp;GeneralTransform3,<br>
&nbsp;&nbsp;&nbsp;&nbsp;Screw3,<br>
&nbsp;&nbsp;&nbsp;&nbsp;AABB,<br>
)<br>
<br>
from&nbsp;.pose2&nbsp;import&nbsp;Pose2<br>
from&nbsp;.screw&nbsp;import&nbsp;Screw,&nbsp;Screw2<br>
from&nbsp;.transform_aabb&nbsp;import&nbsp;TransformAABB<br>
from&nbsp;termin.colliders._colliders_native&nbsp;import&nbsp;Ray3<br>
<br>
__all__&nbsp;=&nbsp;[<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Vec3',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Vec4',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Quat',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Mat44',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Mat44f',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Pose2',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Pose3',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'GeneralPose3',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'GeneralTransform3',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Screw',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Screw2',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Screw3',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'AABB',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'TransformAABB',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Ray3',<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
