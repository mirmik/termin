<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/geombase/ray.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import&nbsp;numpy&nbsp;as&nbsp;np<br>
<br>
class&nbsp;Ray3:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Простой&nbsp;луч&nbsp;в&nbsp;3D:<br>
&nbsp;&nbsp;&nbsp;&nbsp;origin&nbsp;—&nbsp;начало<br>
&nbsp;&nbsp;&nbsp;&nbsp;direction&nbsp;—&nbsp;нормализованное&nbsp;направление<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;origin:&nbsp;np.ndarray,&nbsp;direction:&nbsp;np.ndarray):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.origin&nbsp;=&nbsp;np.asarray(origin,&nbsp;dtype=np.float32)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;d&nbsp;=&nbsp;np.asarray(direction,&nbsp;dtype=np.float32)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;n&nbsp;=&nbsp;np.linalg.norm(d)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.direction&nbsp;=&nbsp;d&nbsp;/&nbsp;n&nbsp;if&nbsp;n&nbsp;&gt;&nbsp;1e-8&nbsp;else&nbsp;np.array([0,&nbsp;0,&nbsp;1],&nbsp;dtype=np.float32)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;point_at(self,&nbsp;t:&nbsp;float):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Возвращает&nbsp;точку&nbsp;на&nbsp;луче&nbsp;при&nbsp;параметре&nbsp;t:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;P(t)&nbsp;=&nbsp;origin&nbsp;+&nbsp;direction&nbsp;*&nbsp;t<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.origin&nbsp;+&nbsp;self.direction&nbsp;*&nbsp;float(t)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__repr__(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;f&quot;Ray3(origin={self.origin},&nbsp;direction={self.direction})&quot;<br>
<!-- END SCAT CODE -->
</body>
</html>
