<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/raycast_hit.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
class&nbsp;RaycastHit:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Результат&nbsp;пересечения&nbsp;луча&nbsp;с&nbsp;объектом&nbsp;сцены.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;entity,&nbsp;component,&nbsp;point,&nbsp;collider_point,&nbsp;distance):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.entity&nbsp;=&nbsp;entity<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.component&nbsp;=&nbsp;component<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.point&nbsp;=&nbsp;point<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.collider_point&nbsp;=&nbsp;collider_point<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.distance&nbsp;=&nbsp;float(distance)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__repr__(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;(f&quot;RaycastHit(entity={self.entity},&nbsp;distance={self.distance},&nbsp;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;f&quot;point={self.point},&nbsp;collider_point={self.collider_point})&quot;)<br>
<!-- END SCAT CODE -->
</body>
</html>
