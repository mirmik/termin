<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/attached.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
from&nbsp;termin.geombase&nbsp;import&nbsp;Pose3<br>
from&nbsp;termin.colliders.collider&nbsp;import&nbsp;Collider<br>
from&nbsp;termin.kinematic&nbsp;import&nbsp;Transform3<br>
import&nbsp;numpy<br>
<br>
class&nbsp;AttachedCollider:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;A&nbsp;collider&nbsp;attached&nbsp;to&nbsp;a&nbsp;Transform3&nbsp;with&nbsp;a&nbsp;local&nbsp;pose.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;collider:&nbsp;Collider,&nbsp;transform:&nbsp;'Transform3',&nbsp;local_pose:&nbsp;Pose3&nbsp;=&nbsp;Pose3.identity()):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self._transform&nbsp;=&nbsp;transform<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self._local_pose&nbsp;=&nbsp;local_pose<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self._collider&nbsp;=&nbsp;collider<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;transformed_collider(self)&nbsp;-&gt;&nbsp;Collider:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Get&nbsp;the&nbsp;collider&nbsp;in&nbsp;world&nbsp;coordinates.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;world_transform&nbsp;=&nbsp;self._transform.global_pose()&nbsp;*&nbsp;self._local_pose<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;wcol&nbsp;=&nbsp;self._collider.transform_by(world_transform)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;wcol<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;local_pose(self)&nbsp;-&gt;&nbsp;Pose3:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Get&nbsp;the&nbsp;local&nbsp;pose&nbsp;of&nbsp;the&nbsp;collider.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self._local_pose<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;transform(self)&nbsp;-&gt;&nbsp;'Transform3':<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Get&nbsp;the&nbsp;Transform3&nbsp;to&nbsp;which&nbsp;this&nbsp;collider&nbsp;is&nbsp;attached.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self._transform<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;distance(self,&nbsp;other:&nbsp;&quot;AttachedCollider&quot;)&nbsp;-&gt;&nbsp;float:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Return&nbsp;the&nbsp;distance&nbsp;between&nbsp;this&nbsp;attached&nbsp;collider&nbsp;and&nbsp;another&nbsp;attached&nbsp;collider.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.transformed_collider().distance(other.transformed_collider())<br>
&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;closest_to_ray(self,&nbsp;ray:&nbsp;&quot;Ray3&quot;):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Делегируем&nbsp;вычисление&nbsp;трансформированному&nbsp;коллайдеру.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.transformed_collider().closest_to_ray(ray)<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;closest_to_collider(self,&nbsp;other:&nbsp;&quot;AttachedCollider&quot;):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Return&nbsp;the&nbsp;closest&nbsp;points&nbsp;and&nbsp;distance&nbsp;between&nbsp;this&nbsp;attached&nbsp;collider&nbsp;and&nbsp;another&nbsp;attached&nbsp;collider.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.transformed_collider().closest_to_collider(other.transformed_collider())<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;avoidance(self,&nbsp;other:&nbsp;&quot;AttachedCollider&quot;)&nbsp;-&gt;&nbsp;numpy.ndarray:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Compute&nbsp;an&nbsp;avoidance&nbsp;vector&nbsp;to&nbsp;maintain&nbsp;a&nbsp;minimum&nbsp;distance&nbsp;from&nbsp;another&nbsp;attached&nbsp;collider.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self.transformed_collider().avoidance(other.transformed_collider())<br>
<!-- END SCAT CODE -->
</body>
</html>
