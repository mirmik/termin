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
    &quot;&quot;&quot;Create a Transform3 or KinematicTransform3 from a Trent dictionary representation.&quot;&quot;&quot;<br>
    ttype = dct.get(&quot;type&quot;, &quot;transform&quot;)<br>
    local_pose_dict = dct.get(&quot;pose&quot;, {})<br>
    position = numpy.array(local_pose_dict.get(&quot;position&quot;, [0.0, 0.0, 0.0]))<br>
    orientation = numpy.array(local_pose_dict.get(&quot;orientation&quot;, [0.0, 0.0, 0.0, 1.0]))<br>
    local_pose = Pose3(lin=position, ang=orientation)<br>
    name = dct.get(&quot;name&quot;, &quot;&quot;)<br>
    <br>
    if ttype == &quot;transform&quot;:<br>
        transform = Transform3(local_pose=local_pose, name=name)<br>
    elif ttype == &quot;rotator&quot;:<br>
        axis = numpy.array(dct.get(&quot;axis&quot;, [0.0, 0.0, 1.0]))<br>
        transform = Rotator3(axis=axis, parent=None, name=name, local_pose=local_pose, manual_output=True)<br>
    elif ttype == &quot;actuator&quot;:<br>
        axis = numpy.array(dct.get(&quot;axis&quot;, [0.0, 0.0, 1.0]))<br>
        transform = Actuator3(axis=axis, parent=None, name=name, local_pose=local_pose, manual_output=True)<br>
    else:<br>
        raise ValueError(f&quot;Unknown transform type: {ttype}&quot;)<br>
    <br>
    for child_dct in dct.get(&quot;children&quot;, []):<br>
        child_transform = from_trent(child_dct)<br>
        transform.add_child(child_transform)<br>
    <br>
    return transform<br>
<!-- END SCAT CODE -->
</body>
</html>
