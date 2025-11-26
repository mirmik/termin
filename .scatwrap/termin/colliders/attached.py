<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/attached.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
from termin.geombase import Pose3<br>
from termin.colliders.collider import Collider<br>
from termin.kinematic import Transform3<br>
import numpy<br>
<br>
class AttachedCollider:<br>
    &quot;&quot;&quot;A collider attached to a Transform3 with a local pose.&quot;&quot;&quot;<br>
    def __init__(self, collider: Collider, transform: 'Transform3', local_pose: Pose3 = Pose3.identity()):<br>
        self._transform = transform<br>
        self._local_pose = local_pose<br>
        self._collider = collider<br>
<br>
    def transformed_collider(self) -&gt; Collider:<br>
        &quot;&quot;&quot;Get the collider in world coordinates.&quot;&quot;&quot;<br>
        world_transform = self._transform.global_pose() * self._local_pose<br>
        wcol = self._collider.transform_by(world_transform)<br>
        return wcol<br>
<br>
    def local_pose(self) -&gt; Pose3:<br>
        &quot;&quot;&quot;Get the local pose of the collider.&quot;&quot;&quot;<br>
        return self._local_pose<br>
<br>
    def transform(self) -&gt; 'Transform3':<br>
        &quot;&quot;&quot;Get the Transform3 to which this collider is attached.&quot;&quot;&quot;<br>
        return self._transform<br>
<br>
    def distance(self, other: &quot;AttachedCollider&quot;) -&gt; float:<br>
        &quot;&quot;&quot;Return the distance between this attached collider and another attached collider.&quot;&quot;&quot;<br>
        return self.transformed_collider().distance(other.transformed_collider())<br>
 <br>
    def closest_to_ray(self, ray: &quot;Ray3&quot;):<br>
        &quot;&quot;&quot;<br>
        Делегируем вычисление трансформированному коллайдеру.<br>
        &quot;&quot;&quot;<br>
        return self.transformed_collider().closest_to_ray(ray)<br>
    <br>
    def closest_to_collider(self, other: &quot;AttachedCollider&quot;):<br>
        &quot;&quot;&quot;Return the closest points and distance between this attached collider and another attached collider.&quot;&quot;&quot;<br>
        return self.transformed_collider().closest_to_collider(other.transformed_collider())<br>
<br>
    def avoidance(self, other: &quot;AttachedCollider&quot;) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Compute an avoidance vector to maintain a minimum distance from another attached collider.&quot;&quot;&quot;<br>
        return self.transformed_collider().avoidance(other.transformed_collider())<br>
<!-- END SCAT CODE -->
</body>
</html>
