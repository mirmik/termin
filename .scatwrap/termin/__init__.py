<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/__init__.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;<br>
Termin&nbsp;-&nbsp;библиотека&nbsp;для&nbsp;кинематики,&nbsp;динамики&nbsp;и&nbsp;мультифизического&nbsp;моделирования.<br>
<br>
Основные&nbsp;модули:<br>
-&nbsp;geombase&nbsp;-&nbsp;базовые&nbsp;геометрические&nbsp;классы&nbsp;(Pose3,&nbsp;Screw2,&nbsp;Screw3)<br>
-&nbsp;kinematics&nbsp;-&nbsp;трансформации&nbsp;и&nbsp;кинематические&nbsp;цепи<br>
-&nbsp;fem&nbsp;-&nbsp;метод&nbsp;конечных&nbsp;элементов&nbsp;для&nbsp;мультифизики<br>
&quot;&quot;&quot;<br>
<br>
#&nbsp;Setup&nbsp;DLL&nbsp;paths&nbsp;before&nbsp;importing&nbsp;native&nbsp;extensions<br>
from&nbsp;termin&nbsp;import&nbsp;_dll_setup&nbsp;&nbsp;#&nbsp;noqa:&nbsp;F401<br>
<br>
#&nbsp;Базовая&nbsp;геометрия<br>
from&nbsp;.geombase&nbsp;import&nbsp;Pose3,&nbsp;Screw2,&nbsp;Screw3<br>
<br>
__version__&nbsp;=&nbsp;'0.1.0'<br>
<br>
__all__&nbsp;=&nbsp;[<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Geombase<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Pose3',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Screw2',<br>
&nbsp;&nbsp;&nbsp;&nbsp;'Screw3',<br>
]<br>
<!-- END SCAT CODE -->
</body>
</html>
