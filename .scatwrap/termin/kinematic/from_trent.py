<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/kinematic/from_trent.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from .transform import Transform3<br>
from .kinematic import KinematicTransform3OneScrew, Rotator3, Actuator3<br>
from termin.geombase import Pose3, Screw3<br>
import numpy<br>
<br>
def from_trent(dct: dict) -&gt; Transform3:<br>
&#9;&quot;&quot;&quot;Create a Transform3 or KinematicTransform3 from a Trent dictionary representation.&quot;&quot;&quot;<br>
&#9;ttype = dct.get(&quot;type&quot;, &quot;transform&quot;)<br>
&#9;local_pose_dict = dct.get(&quot;pose&quot;, {})<br>
&#9;position = numpy.array(local_pose_dict.get(&quot;position&quot;, [0.0, 0.0, 0.0]))<br>
&#9;orientation = numpy.array(local_pose_dict.get(&quot;orientation&quot;, [0.0, 0.0, 0.0, 1.0]))<br>
&#9;local_pose = Pose3(lin=position, ang=orientation)<br>
&#9;name = dct.get(&quot;name&quot;, &quot;&quot;)<br>
&#9;<br>
&#9;if ttype == &quot;transform&quot;:<br>
&#9;&#9;transform = Transform3(local_pose=local_pose, name=name)<br>
&#9;elif ttype == &quot;rotator&quot;:<br>
&#9;&#9;axis = numpy.array(dct.get(&quot;axis&quot;, [0.0, 0.0, 1.0]))<br>
&#9;&#9;transform = Rotator3(axis=axis, parent=None, name=name, local_pose=local_pose, manual_output=True)<br>
&#9;elif ttype == &quot;actuator&quot;:<br>
&#9;&#9;axis = numpy.array(dct.get(&quot;axis&quot;, [0.0, 0.0, 1.0]))<br>
&#9;&#9;transform = Actuator3(axis=axis, parent=None, name=name, local_pose=local_pose, manual_output=True)<br>
&#9;else:<br>
&#9;&#9;raise ValueError(f&quot;Unknown transform type: {ttype}&quot;)<br>
&#9;<br>
&#9;for child_dct in dct.get(&quot;children&quot;, []):<br>
&#9;&#9;child_transform = from_trent(child_dct)<br>
&#9;&#9;transform.add_child(child_transform)<br>
&#9;<br>
&#9;return transform<br>
<!-- END SCAT CODE -->
</body>
</html>
