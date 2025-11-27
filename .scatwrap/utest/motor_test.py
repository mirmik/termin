<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>utest/motor_test.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import&nbsp;unittest<br>
from&nbsp;termin.ga201.motor&nbsp;import&nbsp;Motor2<br>
import&nbsp;math<br>
<br>
<br>
def&nbsp;early(a,&nbsp;b):<br>
&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;abs(a.x&nbsp;-&nbsp;b.x)&nbsp;&gt;&nbsp;0.0001:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;False<br>
&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;abs(a.y&nbsp;-&nbsp;b.y)&nbsp;&gt;&nbsp;0.0001:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;False<br>
&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;abs(a.z&nbsp;-&nbsp;b.z)&nbsp;&gt;&nbsp;0.0001:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;False<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;True<br>
<br>
<br>
class&nbsp;TransformationProbe(unittest.TestCase):<br>
&nbsp;&nbsp;&nbsp;&nbsp;def&nbsp;test_translate(self):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ident&nbsp;=&nbsp;Motor2(0,0,0,1)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;translate&nbsp;=&nbsp;Motor2(1,0,0,1)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertEqual(translate.factorize_translation(),&nbsp;translate)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertEqual(translate.factorize_rotation(),&nbsp;ident)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;rotation&nbsp;=&nbsp;Motor2.rotation(math.pi/2)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertEqual(rotation.factorize_rotation(),&nbsp;rotation)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertEqual(rotation.factorize_translation(),&nbsp;ident)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;q&nbsp;=&nbsp;rotation&nbsp;*&nbsp;translate<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertTrue(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;(q.factorize_translation()&nbsp;-&nbsp;Motor2(0,1,0,1)).is_zero_equal()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;invq&nbsp;=&nbsp;q.inverse()<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;q_invq&nbsp;=&nbsp;q&nbsp;*&nbsp;invq<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;invq_q&nbsp;=&nbsp;invq&nbsp;*&nbsp;q<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertTrue((invq_q&nbsp;-&nbsp;ident).is_zero_equal())<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertTrue((q_invq&nbsp;-&nbsp;ident).is_zero_equal())<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;self.assertTrue((translate.inverse()-Motor2(-1,0,0,1)).is_zero_equal())<br>
<!-- END SCAT CODE -->
</body>
</html>
