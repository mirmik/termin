<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ARCHIVE/physics/pose_object.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import numpy<br>
from termin.ga201.motor import Motor2<br>
<br>
<br>
class PoseObject:<br>
&#9;def __init__(self, pose=Motor2()):<br>
&#9;&#9;self._position = pose<br>
<br>
&#9;def position(self):<br>
&#9;&#9;return self._position<br>
<br>
&#9;def update_position(self, pose):<br>
&#9;&#9;self._position = pose<br>
<br>
<br>
class ReferencedPoseObject:<br>
&#9;def __init__(self, pose=Motor2(), parent=None):<br>
&#9;&#9;self._pose_in_frame = pose<br>
&#9;&#9;self._parent = parent<br>
<br>
&#9;def position(self):<br>
&#9;&#9;return self._parent.position() * self._pose_in_frame<br>
<br>
&#9;def relative_position(self):<br>
&#9;&#9;return self._pose_in_frame<br>
<br>
&#9;def parent(self):<br>
&#9;&#9;return self._parent<br>
<!-- END SCAT CODE -->
</body>
</html>
