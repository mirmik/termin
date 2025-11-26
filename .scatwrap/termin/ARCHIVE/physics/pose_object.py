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
    def __init__(self, pose=Motor2()):<br>
        self._position = pose<br>
<br>
    def position(self):<br>
        return self._position<br>
<br>
    def update_position(self, pose):<br>
        self._position = pose<br>
<br>
<br>
class ReferencedPoseObject:<br>
    def __init__(self, pose=Motor2(), parent=None):<br>
        self._pose_in_frame = pose<br>
        self._parent = parent<br>
<br>
    def position(self):<br>
        return self._parent.position() * self._pose_in_frame<br>
<br>
    def relative_position(self):<br>
        return self._pose_in_frame<br>
<br>
    def parent(self):<br>
        return self._parent<br>
<!-- END SCAT CODE -->
</body>
</html>
