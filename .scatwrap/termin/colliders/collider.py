<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/collider.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
import&nbsp;numpy<br>
<br>
class&nbsp;Collider:<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;closest_to_ray(self,&nbsp;ray:&nbsp;&quot;Ray3&quot;):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Возвращает&nbsp;(p_col,&nbsp;p_ray,&nbsp;distance)&nbsp;—&nbsp;ближайшие&nbsp;точки&nbsp;между&nbsp;коллайдером&nbsp;и&nbsp;лучом.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;raise&nbsp;NotImplementedError(&quot;closest_to_ray&nbsp;must&nbsp;be&nbsp;implemented&nbsp;by&nbsp;subclasses.&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;transform_by(self,&nbsp;transform:&nbsp;'Pose3'):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Return&nbsp;a&nbsp;new&nbsp;Collider&nbsp;transformed&nbsp;by&nbsp;the&nbsp;given&nbsp;Pose3.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;raise&nbsp;NotImplementedError(&quot;transform_by&nbsp;must&nbsp;be&nbsp;implemented&nbsp;by&nbsp;subclasses.&quot;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;closest_to_collider(self,&nbsp;other:&nbsp;&quot;Collider&quot;):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Return&nbsp;the&nbsp;closest&nbsp;points&nbsp;and&nbsp;distance&nbsp;between&nbsp;this&nbsp;collider&nbsp;and&nbsp;another&nbsp;collider.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;raise&nbsp;NotImplementedError(&quot;closest_to_collider&nbsp;must&nbsp;be&nbsp;implemented&nbsp;by&nbsp;subclasses.&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;avoidance(self,&nbsp;other:&nbsp;&quot;Collider&quot;)&nbsp;-&gt;&nbsp;numpy.ndarray:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Compute&nbsp;an&nbsp;avoidance&nbsp;vector&nbsp;to&nbsp;maintain&nbsp;a&nbsp;minimum&nbsp;distance&nbsp;from&nbsp;another&nbsp;collider.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;p_near,&nbsp;q_near,&nbsp;dist&nbsp;=&nbsp;self.closest_to_collider(other)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;diff&nbsp;=&nbsp;p_near&nbsp;-&nbsp;q_near<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;real_dist&nbsp;=&nbsp;numpy.linalg.norm(diff)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;real_dist&nbsp;==&nbsp;0.0:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;numpy.zeros(3),&nbsp;0.0,&nbsp;p_near<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;direction&nbsp;=&nbsp;diff&nbsp;/&nbsp;real_dist<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;direction,&nbsp;real_dist,&nbsp;p_near<br>
<!-- END SCAT CODE -->
</body>
</html>
