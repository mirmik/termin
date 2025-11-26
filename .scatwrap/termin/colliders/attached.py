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
&#9;&quot;&quot;&quot;A collider attached to a Transform3 with a local pose.&quot;&quot;&quot;<br>
&#9;def __init__(self, collider: Collider, transform: 'Transform3', local_pose: Pose3 = Pose3.identity()):<br>
&#9;&#9;self._transform = transform<br>
&#9;&#9;self._local_pose = local_pose<br>
&#9;&#9;self._collider = collider<br>
<br>
&#9;def transformed_collider(self) -&gt; Collider:<br>
&#9;&#9;&quot;&quot;&quot;Get the collider in world coordinates.&quot;&quot;&quot;<br>
&#9;&#9;world_transform = self._transform.global_pose() * self._local_pose<br>
&#9;&#9;wcol = self._collider.transform_by(world_transform)<br>
&#9;&#9;return wcol<br>
<br>
&#9;def local_pose(self) -&gt; Pose3:<br>
&#9;&#9;&quot;&quot;&quot;Get the local pose of the collider.&quot;&quot;&quot;<br>
&#9;&#9;return self._local_pose<br>
<br>
&#9;def transform(self) -&gt; 'Transform3':<br>
&#9;&#9;&quot;&quot;&quot;Get the Transform3 to which this collider is attached.&quot;&quot;&quot;<br>
&#9;&#9;return self._transform<br>
<br>
&#9;def distance(self, other: &quot;AttachedCollider&quot;) -&gt; float:<br>
&#9;&#9;&quot;&quot;&quot;Return the distance between this attached collider and another attached collider.&quot;&quot;&quot;<br>
&#9;&#9;return self.transformed_collider().distance(other.transformed_collider())<br>
<br>
&#9;def closest_to_ray(self, ray: &quot;Ray3&quot;):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Делегируем вычисление трансформированному коллайдеру.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;return self.transformed_collider().closest_to_ray(ray)<br>
&#9;<br>
&#9;def closest_to_collider(self, other: &quot;AttachedCollider&quot;):<br>
&#9;&#9;&quot;&quot;&quot;Return the closest points and distance between this attached collider and another attached collider.&quot;&quot;&quot;<br>
&#9;&#9;return self.transformed_collider().closest_to_collider(other.transformed_collider())<br>
<br>
&#9;def avoidance(self, other: &quot;AttachedCollider&quot;) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Compute an avoidance vector to maintain a minimum distance from another attached collider.&quot;&quot;&quot;<br>
&#9;&#9;return self.transformed_collider().avoidance(other.transformed_collider())<br>
<!-- END SCAT CODE -->
</body>
</html>
