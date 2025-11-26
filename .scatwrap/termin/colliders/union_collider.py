<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/union_collider.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from&nbsp;termin.colliders.collider&nbsp;import&nbsp;Collider<br>
import&nbsp;numpy<br>
<br>
class&nbsp;UnionCollider(Collider):<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;closest_to_ray(self,&nbsp;ray:&nbsp;&quot;Ray3&quot;):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;min_dist&nbsp;=&nbsp;float(&quot;inf&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;best_p&nbsp;=&nbsp;None<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;best_q&nbsp;=&nbsp;None<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;col&nbsp;in&nbsp;self.colliders:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;p,&nbsp;q,&nbsp;d&nbsp;=&nbsp;col.closest_to_ray(ray)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;d&nbsp;&lt;&nbsp;min_dist:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;min_dist&nbsp;=&nbsp;d<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;best_p&nbsp;=&nbsp;p<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;best_q&nbsp;=&nbsp;q<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;best_p,&nbsp;best_q,&nbsp;min_dist<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;colliders):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.colliders&nbsp;=&nbsp;colliders<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;transform_by(self,&nbsp;transform:&nbsp;'Pose3'):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Return&nbsp;a&nbsp;new&nbsp;UnionCollider&nbsp;transformed&nbsp;by&nbsp;the&nbsp;given&nbsp;Transform3.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;transformed_colliders&nbsp;=&nbsp;[collider.transform_by(transform)&nbsp;for&nbsp;collider&nbsp;in&nbsp;self.colliders]<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;UnionCollider(transformed_colliders)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;closest_to_collider(self,&nbsp;other:&nbsp;&quot;Collider&quot;):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Return&nbsp;the&nbsp;closest&nbsp;points&nbsp;and&nbsp;distance&nbsp;between&nbsp;this&nbsp;union&nbsp;collider&nbsp;and&nbsp;another&nbsp;collider.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;min_dist&nbsp;=&nbsp;float('inf')<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;closest_p&nbsp;=&nbsp;None<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;closest_q&nbsp;=&nbsp;None<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;collider&nbsp;in&nbsp;self.colliders:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;p_near,&nbsp;q_near,&nbsp;dist&nbsp;=&nbsp;collider.closest_to_collider(other)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;dist&nbsp;&lt;&nbsp;min_dist:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;min_dist&nbsp;=&nbsp;dist<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;closest_p&nbsp;=&nbsp;p_near<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;closest_q&nbsp;=&nbsp;q_near<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;closest_p,&nbsp;closest_q,&nbsp;min_dist<br>
<!-- END SCAT CODE -->
</body>
</html>
