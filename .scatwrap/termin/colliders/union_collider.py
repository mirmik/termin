<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/union_collider.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from termin.colliders.collider import Collider<br>
import numpy<br>
<br>
class UnionCollider(Collider):<br>
    def closest_to_ray(self, ray: &quot;Ray3&quot;):<br>
        min_dist = float(&quot;inf&quot;)<br>
        best_p = None<br>
        best_q = None<br>
<br>
        for col in self.colliders:<br>
            p, q, d = col.closest_to_ray(ray)<br>
            if d &lt; min_dist:<br>
                min_dist = d<br>
                best_p = p<br>
                best_q = q<br>
<br>
        return best_p, best_q, min_dist<br>
    def __init__(self, colliders):<br>
        self.colliders = colliders<br>
<br>
    def transform_by(self, transform: 'Pose3'):<br>
        &quot;&quot;&quot;Return a new UnionCollider transformed by the given Transform3.&quot;&quot;&quot;<br>
        transformed_colliders = [collider.transform_by(transform) for collider in self.colliders]<br>
        return UnionCollider(transformed_colliders)<br>
<br>
    def closest_to_collider(self, other: &quot;Collider&quot;):<br>
        &quot;&quot;&quot;Return the closest points and distance between this union collider and another collider.&quot;&quot;&quot;<br>
        min_dist = float('inf')<br>
        closest_p = None<br>
        closest_q = None<br>
<br>
        for collider in self.colliders:<br>
            p_near, q_near, dist = collider.closest_to_collider(other)<br>
            if dist &lt; min_dist:<br>
                min_dist = dist<br>
                closest_p = p_near<br>
                closest_q = q_near<br>
<br>
        return closest_p, closest_q, min_dist<br>
<!-- END SCAT CODE -->
</body>
</html>
