<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>utest/kinematics/kinematic_test.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import&nbsp;unittest<br>
from&nbsp;termin.kinematic&nbsp;import&nbsp;*<br>
from&nbsp;termin.kinematic&nbsp;import&nbsp;Transform3<br>
from&nbsp;termin.geombase&nbsp;import&nbsp;Pose3<br>
import&nbsp;numpy<br>
import&nbsp;math<br>
<br>
class&nbsp;TestRotator3(unittest.TestCase):<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_rotation(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rotator&nbsp;=&nbsp;Rotator3(axis=numpy.array([0,&nbsp;0,&nbsp;1]))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;trsf&nbsp;=&nbsp;Transform3(Pose3.translation(1.0,&nbsp;0.0,&nbsp;0.0))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rotator.link(trsf)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;angle&nbsp;=&nbsp;math.pi&nbsp;/&nbsp;2&nbsp;&nbsp;#&nbsp;90&nbsp;degrees<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rotator.set_coord(angle)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rotated_point&nbsp;=&nbsp;trsf.transform_point(numpy.array([1.0,&nbsp;0.0,&nbsp;0.0]))<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;expected_point&nbsp;=&nbsp;numpy.array([0.0,&nbsp;2.0,&nbsp;0.0])<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;numpy.testing.assert_array_almost_equal(rotated_point,&nbsp;expected_point)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;check&nbsp;childs<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;count_of_rotator_childs&nbsp;=&nbsp;len(rotator.children)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertEqual(count_of_rotator_childs,&nbsp;1)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;count_of_rotator_output_childs&nbsp;=&nbsp;len(rotator.children)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertEqual(count_of_rotator_output_childs,&nbsp;1)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;count_of_trsf_childs&nbsp;=&nbsp;len(trsf.children)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertEqual(count_of_trsf_childs,&nbsp;0)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;check&nbsp;parent<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIs(trsf.parent,&nbsp;rotator.output)&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIs(rotator.output.parent,&nbsp;rotator)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertIsNone(rotator.parent)<br>
<!-- END SCAT CODE -->
</body>
</html>
