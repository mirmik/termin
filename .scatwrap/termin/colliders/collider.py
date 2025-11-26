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
    def closest_to_ray(self, ray: &quot;Ray3&quot;):<br>
        &quot;&quot;&quot;<br>
        Возвращает (p_col, p_ray, distance) — ближайшие точки между коллайдером и лучом.<br>
        &quot;&quot;&quot;<br>
        raise NotImplementedError(&quot;closest_to_ray must be implemented by subclasses.&quot;)<br>
    <br>
    def transform_by(self, transform: 'Pose3'):<br>
        &quot;&quot;&quot;Return a new Collider transformed by the given Pose3.&quot;&quot;&quot;<br>
        raise NotImplementedError(&quot;transform_by must be implemented by subclasses.&quot;)<br>
<br>
    def closest_to_collider(self, other: &quot;Collider&quot;):<br>
        &quot;&quot;&quot;Return the closest points and distance between this collider and another collider.&quot;&quot;&quot;<br>
        raise NotImplementedError(&quot;closest_to_collider must be implemented by subclasses.&quot;)<br>
    <br>
    def avoidance(self, other: &quot;Collider&quot;) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Compute an avoidance vector to maintain a minimum distance from another collider.&quot;&quot;&quot;<br>
        p_near, q_near, dist = self.closest_to_collider(other)<br>
        diff = p_near - q_near<br>
        real_dist = numpy.linalg.norm(diff)<br>
        if real_dist == 0.0:<br>
            return numpy.zeros(3), 0.0, p_near<br>
        direction = diff / real_dist<br>
        return direction, real_dist, p_near<br>
<!-- END SCAT CODE -->
</body>
</html>
