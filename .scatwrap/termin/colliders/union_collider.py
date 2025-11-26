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
&#9;def closest_to_ray(self, ray: &quot;Ray3&quot;):<br>
&#9;&#9;min_dist = float(&quot;inf&quot;)<br>
&#9;&#9;best_p = None<br>
&#9;&#9;best_q = None<br>
<br>
&#9;&#9;for col in self.colliders:<br>
&#9;&#9;&#9;p, q, d = col.closest_to_ray(ray)<br>
&#9;&#9;&#9;if d &lt; min_dist:<br>
&#9;&#9;&#9;&#9;min_dist = d<br>
&#9;&#9;&#9;&#9;best_p = p<br>
&#9;&#9;&#9;&#9;best_q = q<br>
<br>
&#9;&#9;return best_p, best_q, min_dist<br>
&#9;def __init__(self, colliders):<br>
&#9;&#9;self.colliders = colliders<br>
<br>
&#9;def transform_by(self, transform: 'Pose3'):<br>
&#9;&#9;&quot;&quot;&quot;Return a new UnionCollider transformed by the given Transform3.&quot;&quot;&quot;<br>
&#9;&#9;transformed_colliders = [collider.transform_by(transform) for collider in self.colliders]<br>
&#9;&#9;return UnionCollider(transformed_colliders)<br>
<br>
&#9;def closest_to_collider(self, other: &quot;Collider&quot;):<br>
&#9;&#9;&quot;&quot;&quot;Return the closest points and distance between this union collider and another collider.&quot;&quot;&quot;<br>
&#9;&#9;min_dist = float('inf')<br>
&#9;&#9;closest_p = None<br>
&#9;&#9;closest_q = None<br>
<br>
&#9;&#9;for collider in self.colliders:<br>
&#9;&#9;&#9;p_near, q_near, dist = collider.closest_to_collider(other)<br>
&#9;&#9;&#9;if dist &lt; min_dist:<br>
&#9;&#9;&#9;&#9;min_dist = dist<br>
&#9;&#9;&#9;&#9;closest_p = p_near<br>
&#9;&#9;&#9;&#9;closest_q = q_near<br>
<br>
&#9;&#9;return closest_p, closest_q, min_dist<br>
<!-- END SCAT CODE -->
</body>
</html>
