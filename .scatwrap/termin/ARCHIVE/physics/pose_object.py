<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ARCHIVE/physics/pose_object.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import&nbsp;numpy<br>
from&nbsp;termin.ga201.motor&nbsp;import&nbsp;Motor2<br>
<br>
<br>
class&nbsp;PoseObject:<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;pose=Motor2()):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self._position&nbsp;=&nbsp;pose<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;position(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self._position<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;update_position(self,&nbsp;pose):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self._position&nbsp;=&nbsp;pose<br>
<br>
<br>
class&nbsp;ReferencedPoseObject:<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;__init__(self,&nbsp;pose=Motor2(),&nbsp;parent=None):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self._pose_in_frame&nbsp;=&nbsp;pose<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self._parent&nbsp;=&nbsp;parent<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;position(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self._parent.position()&nbsp;*&nbsp;self._pose_in_frame<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;relative_position(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self._pose_in_frame<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;parent(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;self._parent<br>
<!-- END SCAT CODE -->
</body>
</html>
