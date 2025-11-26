<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/attached.py</title>
</head>
<body>
<pre><code>

from termin.geombase import Pose3
from termin.colliders.collider import Collider
from termin.kinematic import Transform3
import numpy

class AttachedCollider:
    &quot;&quot;&quot;A collider attached to a Transform3 with a local pose.&quot;&quot;&quot;
    def __init__(self, collider: Collider, transform: 'Transform3', local_pose: Pose3 = Pose3.identity()):
        self._transform = transform
        self._local_pose = local_pose
        self._collider = collider

    def transformed_collider(self) -&gt; Collider:
        &quot;&quot;&quot;Get the collider in world coordinates.&quot;&quot;&quot;
        world_transform = self._transform.global_pose() * self._local_pose
        wcol = self._collider.transform_by(world_transform)
        return wcol

    def local_pose(self) -&gt; Pose3:
        &quot;&quot;&quot;Get the local pose of the collider.&quot;&quot;&quot;
        return self._local_pose

    def transform(self) -&gt; 'Transform3':
        &quot;&quot;&quot;Get the Transform3 to which this collider is attached.&quot;&quot;&quot;
        return self._transform

    def distance(self, other: &quot;AttachedCollider&quot;) -&gt; float:
        &quot;&quot;&quot;Return the distance between this attached collider and another attached collider.&quot;&quot;&quot;
        return self.transformed_collider().distance(other.transformed_collider())
 
    def closest_to_ray(self, ray: &quot;Ray3&quot;):
        &quot;&quot;&quot;
        Делегируем вычисление трансформированному коллайдеру.
        &quot;&quot;&quot;
        return self.transformed_collider().closest_to_ray(ray)
    
    def closest_to_collider(self, other: &quot;AttachedCollider&quot;):
        &quot;&quot;&quot;Return the closest points and distance between this attached collider and another attached collider.&quot;&quot;&quot;
        return self.transformed_collider().closest_to_collider(other.transformed_collider())

    def avoidance(self, other: &quot;AttachedCollider&quot;) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Compute an avoidance vector to maintain a minimum distance from another attached collider.&quot;&quot;&quot;
        return self.transformed_collider().avoidance(other.transformed_collider())

</code></pre>
</body>
</html>
