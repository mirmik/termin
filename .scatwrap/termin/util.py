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
    &quot;&quot;&quot;Multiply two quaternions.&quot;&quot;&quot;<br>
    x1, y1, z1, w1 = q1<br>
    x2, y2, z2, w2 = q2<br>
    return numpy.array([<br>
        w1*x2 + x1*w2 + y1*z2 - z1*y2,<br>
        w1*y2 - x1*z2 + y1*w2 + z1*x2,<br>
        w1*z2 + x1*y2 - y1*x2 + z1*w2,<br>
        w1*w2 - x1*x2 - y1*y2 - z1*z2<br>
    ])<br>
<br>
def qmul_vector(q: numpy.ndarray, v: numpy.ndarray) -&gt; numpy.ndarray:<br>
    x1, y1, z1, w1 = q<br>
    x2, y2, z2 = v<br>
    return numpy.array([<br>
        w1*x2         + y1*z2 - z1*y2,<br>
        w1*y2 - x1*z2         + z1*x2,<br>
        w1*z2 + x1*y2 - y1*x2,<br>
              - x1*x2 - y1*y2 - z1*z2<br>
    ])<br>
<br>
<br>
def qrot(q: numpy.ndarray, v: numpy.ndarray) -&gt; numpy.ndarray:<br>
    &quot;&quot;&quot;Rotate vector v by quaternion q.&quot;&quot;&quot;<br>
    q_conj = numpy.array([-q[0], -q[1], -q[2], q[3]])<br>
    rotated_v = qmul(qmul_vector(q, v), q_conj)<br>
    return rotated_v[:3]<br>
<br>
def qslerp(q1: numpy.ndarray, q2: numpy.ndarray, t: float) -&gt; numpy.ndarray:<br>
    &quot;&quot;&quot;Spherical linear interpolation between two quaternions.&quot;&quot;&quot;<br>
    dot = numpy.dot(q1, q2)<br>
    if dot &lt; 0.0:<br>
        q2 = -q2<br>
        dot = -dot<br>
<br>
    DOT_THRESHOLD = 0.9995<br>
    if dot &gt; DOT_THRESHOLD:<br>
        result = q1 + t * (q2 - q1)<br>
        return result / numpy.linalg.norm(result)<br>
<br>
    theta_0 = math.acos(dot)<br>
    theta = theta_0 * t<br>
    sin_theta = math.sin(theta)<br>
    sin_theta_0 = math.sin(theta_0)<br>
<br>
    s1 = math.cos(theta) - dot * sin_theta / sin_theta_0<br>
    s2 = sin_theta / sin_theta_0<br>
<br>
    return (s1 * q1) + (s2 * q2)<br>
<br>
def deg2rad(deg):<br>
    return deg / 180.0 * math.pi<br>
<br>
def qinv(q: numpy.ndarray) -&gt; numpy.ndarray:<br>
    &quot;&quot;&quot;Compute the inverse of a quaternion.&quot;&quot;&quot;<br>
    return numpy.array([-q[0], -q[1], -q[2], q[3]])<br>
<!-- END SCAT CODE -->
</body>
</html>
