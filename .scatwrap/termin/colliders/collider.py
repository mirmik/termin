<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/collider.py</title>
</head>
<body>
<pre><code>

import numpy

class Collider:
    def closest_to_ray(self, ray: &quot;Ray3&quot;):
        &quot;&quot;&quot;
        Возвращает (p_col, p_ray, distance) — ближайшие точки между коллайдером и лучом.
        &quot;&quot;&quot;
        raise NotImplementedError(&quot;closest_to_ray must be implemented by subclasses.&quot;)
    
    def transform_by(self, transform: 'Pose3'):
        &quot;&quot;&quot;Return a new Collider transformed by the given Pose3.&quot;&quot;&quot;
        raise NotImplementedError(&quot;transform_by must be implemented by subclasses.&quot;)

    def closest_to_collider(self, other: &quot;Collider&quot;):
        &quot;&quot;&quot;Return the closest points and distance between this collider and another collider.&quot;&quot;&quot;
        raise NotImplementedError(&quot;closest_to_collider must be implemented by subclasses.&quot;)
    
    def avoidance(self, other: &quot;Collider&quot;) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Compute an avoidance vector to maintain a minimum distance from another collider.&quot;&quot;&quot;
        p_near, q_near, dist = self.closest_to_collider(other)
        diff = p_near - q_near
        real_dist = numpy.linalg.norm(diff)
        if real_dist == 0.0:
            return numpy.zeros(3), 0.0, p_near
        direction = diff / real_dist
        return direction, real_dist, p_near

</code></pre>
</body>
</html>
