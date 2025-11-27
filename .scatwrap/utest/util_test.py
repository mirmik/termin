<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>utest/util_test.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import&nbsp;unittest<br>
from&nbsp;termin.util&nbsp;import&nbsp;*<br>
import&nbsp;numpy<br>
import&nbsp;math<br>
<br>
class&nbsp;TestUtil(unittest.TestCase):<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_slerp(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;q1&nbsp;=&nbsp;numpy.array([0.0,&nbsp;0.0,&nbsp;math.sin(0.0),&nbsp;math.cos(0.0)])&nbsp;&nbsp;#&nbsp;Identity&nbsp;quaternion<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;q2&nbsp;=&nbsp;numpy.array([0.0,&nbsp;0.0,&nbsp;math.sin(math.pi/2),&nbsp;math.cos(math.pi/2)])&nbsp;&nbsp;#&nbsp;90&nbsp;degrees&nbsp;around&nbsp;Z<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;q_halfway&nbsp;=&nbsp;qslerp(q1,&nbsp;q2,&nbsp;0.5)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;expected_halfway&nbsp;=&nbsp;numpy.array([0.0,&nbsp;0.0,&nbsp;math.sin(math.pi/4),&nbsp;math.cos(math.pi/4)])<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;numpy.testing.assert_array_almost_equal(q_halfway,&nbsp;expected_halfway)<br>
<!-- END SCAT CODE -->
</body>
</html>
