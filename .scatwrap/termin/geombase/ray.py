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
    &quot;&quot;&quot;<br>
    Простой луч в 3D:<br>
    origin — начало<br>
    direction — нормализованное направление<br>
    &quot;&quot;&quot;<br>
    def __init__(self, origin: np.ndarray, direction: np.ndarray):<br>
        self.origin = np.asarray(origin, dtype=np.float32)<br>
        d = np.asarray(direction, dtype=np.float32)<br>
        n = np.linalg.norm(d)<br>
        self.direction = d / n if n &gt; 1e-8 else np.array([0, 0, 1], dtype=np.float32)<br>
<br>
    def point_at(self, t: float):<br>
        &quot;&quot;&quot;<br>
        Возвращает точку на луче при параметре t:<br>
        P(t) = origin + direction * t<br>
        &quot;&quot;&quot;<br>
        return self.origin + self.direction * float(t)<br>
<br>
    def __repr__(self):<br>
        return f&quot;Ray3(origin={self.origin}, direction={self.direction})&quot;<br>
<!-- END SCAT CODE -->
</body>
</html>
