<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/union_collider.py</title>
</head>
<body>
<pre><code>
from termin.colliders.collider import Collider
import numpy

class UnionCollider(Collider):
    def closest_to_ray(self, ray: &quot;Ray3&quot;):
        min_dist = float(&quot;inf&quot;)
        best_p = None
        best_q = None

        for col in self.colliders:
            p, q, d = col.closest_to_ray(ray)
            if d &lt; min_dist:
                min_dist = d
                best_p = p
                best_q = q

        return best_p, best_q, min_dist
    def __init__(self, colliders):
        self.colliders = colliders

    def transform_by(self, transform: 'Pose3'):
        &quot;&quot;&quot;Return a new UnionCollider transformed by the given Transform3.&quot;&quot;&quot;
        transformed_colliders = [collider.transform_by(transform) for collider in self.colliders]
        return UnionCollider(transformed_colliders)

    def closest_to_collider(self, other: &quot;Collider&quot;):
        &quot;&quot;&quot;Return the closest points and distance between this union collider and another collider.&quot;&quot;&quot;
        min_dist = float('inf')
        closest_p = None
        closest_q = None

        for collider in self.colliders:
            p_near, q_near, dist = collider.closest_to_collider(other)
            if dist &lt; min_dist:
                min_dist = dist
                closest_p = p_near
                closest_q = q_near

        return closest_p, closest_q, min_dist

</code></pre>
</body>
</html>
