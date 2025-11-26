<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/kinematic/from_trent.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from&nbsp;.transform&nbsp;import&nbsp;Transform3<br>
from&nbsp;.kinematic&nbsp;import&nbsp;KinematicTransform3OneScrew,&nbsp;Rotator3,&nbsp;Actuator3<br>
from&nbsp;termin.geombase&nbsp;import&nbsp;Pose3,&nbsp;Screw3<br>
import&nbsp;numpy<br>
<br>
def&nbsp;from_trent(dct:&nbsp;dict)&nbsp;-&gt;&nbsp;Transform3:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Create&nbsp;a&nbsp;Transform3&nbsp;or&nbsp;KinematicTransform3&nbsp;from&nbsp;a&nbsp;Trent&nbsp;dictionary&nbsp;representation.&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;ttype&nbsp;=&nbsp;dct.get(&quot;type&quot;,&nbsp;&quot;transform&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;local_pose_dict&nbsp;=&nbsp;dct.get(&quot;pose&quot;,&nbsp;{})<br>
&nbsp;&nbsp;&nbsp;&nbsp;position&nbsp;=&nbsp;numpy.array(local_pose_dict.get(&quot;position&quot;,&nbsp;[0.0,&nbsp;0.0,&nbsp;0.0]))<br>
&nbsp;&nbsp;&nbsp;&nbsp;orientation&nbsp;=&nbsp;numpy.array(local_pose_dict.get(&quot;orientation&quot;,&nbsp;[0.0,&nbsp;0.0,&nbsp;0.0,&nbsp;1.0]))<br>
&nbsp;&nbsp;&nbsp;&nbsp;local_pose&nbsp;=&nbsp;Pose3(lin=position,&nbsp;ang=orientation)<br>
&nbsp;&nbsp;&nbsp;&nbsp;name&nbsp;=&nbsp;dct.get(&quot;name&quot;,&nbsp;&quot;&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;ttype&nbsp;==&nbsp;&quot;transform&quot;:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;transform&nbsp;=&nbsp;Transform3(local_pose=local_pose,&nbsp;name=name)<br>
&nbsp;&nbsp;&nbsp;&nbsp;elif&nbsp;ttype&nbsp;==&nbsp;&quot;rotator&quot;:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;axis&nbsp;=&nbsp;numpy.array(dct.get(&quot;axis&quot;,&nbsp;[0.0,&nbsp;0.0,&nbsp;1.0]))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;transform&nbsp;=&nbsp;Rotator3(axis=axis,&nbsp;parent=None,&nbsp;name=name,&nbsp;local_pose=local_pose,&nbsp;manual_output=True)<br>
&nbsp;&nbsp;&nbsp;&nbsp;elif&nbsp;ttype&nbsp;==&nbsp;&quot;actuator&quot;:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;axis&nbsp;=&nbsp;numpy.array(dct.get(&quot;axis&quot;,&nbsp;[0.0,&nbsp;0.0,&nbsp;1.0]))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;transform&nbsp;=&nbsp;Actuator3(axis=axis,&nbsp;parent=None,&nbsp;name=name,&nbsp;local_pose=local_pose,&nbsp;manual_output=True)<br>
&nbsp;&nbsp;&nbsp;&nbsp;else:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;raise&nbsp;ValueError(f&quot;Unknown&nbsp;transform&nbsp;type:&nbsp;{ttype}&quot;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;for&nbsp;child_dct&nbsp;in&nbsp;dct.get(&quot;children&quot;,&nbsp;[]):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;child_transform&nbsp;=&nbsp;from_trent(child_dct)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;transform.add_child(child_transform)<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;transform<br>
<!-- END SCAT CODE -->
</body>
</html>
