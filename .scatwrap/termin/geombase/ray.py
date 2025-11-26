<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/geombase/ray.py</title>
</head>
<body>
<pre><code>
import numpy as np

class Ray3:
    &quot;&quot;&quot;
    Простой луч в 3D:
    origin — начало
    direction — нормализованное направление
    &quot;&quot;&quot;
    def __init__(self, origin: np.ndarray, direction: np.ndarray):
        self.origin = np.asarray(origin, dtype=np.float32)
        d = np.asarray(direction, dtype=np.float32)
        n = np.linalg.norm(d)
        self.direction = d / n if n &gt; 1e-8 else np.array([0, 0, 1], dtype=np.float32)

    def point_at(self, t: float):
        &quot;&quot;&quot;
        Возвращает точку на луче при параметре t:
        P(t) = origin + direction * t
        &quot;&quot;&quot;
        return self.origin + self.direction * float(t)

    def __repr__(self):
        return f&quot;Ray3(origin={self.origin}, direction={self.direction})&quot;
</code></pre>
</body>
</html>
