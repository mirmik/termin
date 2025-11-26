<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/geombase/ray.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import numpy as np<br>
<br>
class Ray3:<br>
&#9;&quot;&quot;&quot;<br>
&#9;Простой луч в 3D:<br>
&#9;origin — начало<br>
&#9;direction — нормализованное направление<br>
&#9;&quot;&quot;&quot;<br>
&#9;def __init__(self, origin: np.ndarray, direction: np.ndarray):<br>
&#9;&#9;self.origin = np.asarray(origin, dtype=np.float32)<br>
&#9;&#9;d = np.asarray(direction, dtype=np.float32)<br>
&#9;&#9;n = np.linalg.norm(d)<br>
&#9;&#9;self.direction = d / n if n &gt; 1e-8 else np.array([0, 0, 1], dtype=np.float32)<br>
<br>
&#9;def point_at(self, t: float):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Возвращает точку на луче при параметре t:<br>
&#9;&#9;P(t) = origin + direction * t<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return self.origin + self.direction * float(t)<br>
<br>
&#9;def __repr__(self):<br>
&#9;&#9;return f&quot;Ray3(origin={self.origin}, direction={self.direction})&quot;<br>
<!-- END SCAT CODE -->
</body>
</html>
