<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/collider.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
import numpy<br>
<br>
class Collider:<br>
&#9;def closest_to_ray(self, ray: &quot;Ray3&quot;):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Возвращает (p_col, p_ray, distance) — ближайшие точки между коллайдером и лучом.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;raise NotImplementedError(&quot;closest_to_ray must be implemented by subclasses.&quot;)<br>
&#9;<br>
&#9;def transform_by(self, transform: 'Pose3'):<br>
&#9;&#9;&quot;&quot;&quot;Return a new Collider transformed by the given Pose3.&quot;&quot;&quot;<br>
&#9;&#9;raise NotImplementedError(&quot;transform_by must be implemented by subclasses.&quot;)<br>
<br>
&#9;def closest_to_collider(self, other: &quot;Collider&quot;):<br>
&#9;&#9;&quot;&quot;&quot;Return the closest points and distance between this collider and another collider.&quot;&quot;&quot;<br>
&#9;&#9;raise NotImplementedError(&quot;closest_to_collider must be implemented by subclasses.&quot;)<br>
&#9;<br>
&#9;def avoidance(self, other: &quot;Collider&quot;) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Compute an avoidance vector to maintain a minimum distance from another collider.&quot;&quot;&quot;<br>
&#9;&#9;p_near, q_near, dist = self.closest_to_collider(other)<br>
&#9;&#9;diff = p_near - q_near<br>
&#9;&#9;real_dist = numpy.linalg.norm(diff)<br>
&#9;&#9;if real_dist == 0.0:<br>
&#9;&#9;&#9;return numpy.zeros(3), 0.0, p_near<br>
&#9;&#9;direction = diff / real_dist<br>
&#9;&#9;return direction, real_dist, p_near<br>
<!-- END SCAT CODE -->
</body>
</html>
