<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/util.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import math<br>
import numpy<br>
<br>
def qmul(q1: numpy.ndarray, q2: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;&quot;&quot;&quot;Multiply two quaternions.&quot;&quot;&quot;<br>
&#9;x1, y1, z1, w1 = q1<br>
&#9;x2, y2, z2, w2 = q2<br>
&#9;return numpy.array([<br>
&#9;&#9;w1*x2 + x1*w2 + y1*z2 - z1*y2,<br>
&#9;&#9;w1*y2 - x1*z2 + y1*w2 + z1*x2,<br>
&#9;&#9;w1*z2 + x1*y2 - y1*x2 + z1*w2,<br>
&#9;&#9;w1*w2 - x1*x2 - y1*y2 - z1*z2<br>
&#9;])<br>
<br>
def qmul_vector(q: numpy.ndarray, v: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;x1, y1, z1, w1 = q<br>
&#9;x2, y2, z2 = v<br>
&#9;return numpy.array([<br>
&#9;&#9;w1*x2         + y1*z2 - z1*y2,<br>
&#9;&#9;w1*y2 - x1*z2         + z1*x2,<br>
&#9;&#9;w1*z2 + x1*y2 - y1*x2,<br>
&#9;&#9;&#9;- x1*x2 - y1*y2 - z1*z2<br>
&#9;])<br>
<br>
<br>
def qrot(q: numpy.ndarray, v: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;&quot;&quot;&quot;Rotate vector v by quaternion q.&quot;&quot;&quot;<br>
&#9;q_conj = numpy.array([-q[0], -q[1], -q[2], q[3]])<br>
&#9;rotated_v = qmul(qmul_vector(q, v), q_conj)<br>
&#9;return rotated_v[:3]<br>
<br>
def qslerp(q1: numpy.ndarray, q2: numpy.ndarray, t: float) -&gt; numpy.ndarray:<br>
&#9;&quot;&quot;&quot;Spherical linear interpolation between two quaternions.&quot;&quot;&quot;<br>
&#9;dot = numpy.dot(q1, q2)<br>
&#9;if dot &lt; 0.0:<br>
&#9;&#9;q2 = -q2<br>
&#9;&#9;dot = -dot<br>
<br>
&#9;DOT_THRESHOLD = 0.9995<br>
&#9;if dot &gt; DOT_THRESHOLD:<br>
&#9;&#9;result = q1 + t * (q2 - q1)<br>
&#9;&#9;return result / numpy.linalg.norm(result)<br>
<br>
&#9;theta_0 = math.acos(dot)<br>
&#9;theta = theta_0 * t<br>
&#9;sin_theta = math.sin(theta)<br>
&#9;sin_theta_0 = math.sin(theta_0)<br>
<br>
&#9;s1 = math.cos(theta) - dot * sin_theta / sin_theta_0<br>
&#9;s2 = sin_theta / sin_theta_0<br>
<br>
&#9;return (s1 * q1) + (s2 * q2)<br>
<br>
def deg2rad(deg):<br>
&#9;return deg / 180.0 * math.pi<br>
<br>
def qinv(q: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;&quot;&quot;&quot;Compute the inverse of a quaternion.&quot;&quot;&quot;<br>
&#9;return numpy.array([-q[0], -q[1], -q[2], q[3]])<br>
&#9;<br>
<!-- END SCAT CODE -->
</body>
</html>
