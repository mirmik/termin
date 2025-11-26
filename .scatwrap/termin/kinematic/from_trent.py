<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/kinematic/from_trent.py</title>
</head>
<body>
<pre><code>
from .transform import Transform3
from .kinematic import KinematicTransform3OneScrew, Rotator3, Actuator3
from termin.geombase import Pose3, Screw3
import numpy

def from_trent(dct: dict) -&gt; Transform3:
    &quot;&quot;&quot;Create a Transform3 or KinematicTransform3 from a Trent dictionary representation.&quot;&quot;&quot;
    ttype = dct.get(&quot;type&quot;, &quot;transform&quot;)
    local_pose_dict = dct.get(&quot;pose&quot;, {})
    position = numpy.array(local_pose_dict.get(&quot;position&quot;, [0.0, 0.0, 0.0]))
    orientation = numpy.array(local_pose_dict.get(&quot;orientation&quot;, [0.0, 0.0, 0.0, 1.0]))
    local_pose = Pose3(lin=position, ang=orientation)
    name = dct.get(&quot;name&quot;, &quot;&quot;)
    
    if ttype == &quot;transform&quot;:
        transform = Transform3(local_pose=local_pose, name=name)
    elif ttype == &quot;rotator&quot;:
        axis = numpy.array(dct.get(&quot;axis&quot;, [0.0, 0.0, 1.0]))
        transform = Rotator3(axis=axis, parent=None, name=name, local_pose=local_pose, manual_output=True)
    elif ttype == &quot;actuator&quot;:
        axis = numpy.array(dct.get(&quot;axis&quot;, [0.0, 0.0, 1.0]))
        transform = Actuator3(axis=axis, parent=None, name=name, local_pose=local_pose, manual_output=True)
    else:
        raise ValueError(f&quot;Unknown transform type: {ttype}&quot;)
    
    for child_dct in dct.get(&quot;children&quot;, []):
        child_transform = from_trent(child_dct)
        transform.add_child(child_transform)
    
    return transform
</code></pre>
</body>
</html>
