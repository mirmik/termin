<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ga201/motor.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
import math<br>
from termin.ga201.point import Point2<br>
from termin.ga201.screw import Screw2<br>
import numpy<br>
<br>
<br>
class Motor2:<br>
&#9;def __init__(self, x=0, y=0, z=0, w=1):<br>
&#9;&#9;self.x = x<br>
&#9;&#9;self.y = y<br>
&#9;&#9;self.z = z<br>
&#9;&#9;self.w = w<br>
<br>
&#9;def self_unitize(self):<br>
&#9;&#9;l = self.z * self.z + self.w * self.w<br>
&#9;&#9;n = math.sqrt(l)<br>
&#9;&#9;return Motor2(self.x / n,<br>
&#9;&#9;&#9;&#9;&#9;self.y / n,<br>
&#9;&#9;&#9;&#9;&#9;self.z / n,<br>
&#9;&#9;&#9;&#9;&#9;self.w / n)<br>
<br>
&#9;def log(self):<br>
&#9;&#9;angle = self.factorize_rotation_angle()<br>
&#9;&#9;translation = self.factorize_translation_vector()<br>
&#9;&#9;return Screw2(angle, translation)<br>
<br>
&#9;@staticmethod<br>
&#9;def rotation(rads):<br>
&#9;&#9;z = math.sin(rads/2)<br>
&#9;&#9;w = math.cos(rads/2)<br>
&#9;&#9;return Motor2(0, 0, z, w)<br>
<br>
&#9;@staticmethod<br>
&#9;def translation(x, y):<br>
&#9;&#9;x = x/2<br>
&#9;&#9;y = y/2<br>
&#9;&#9;z = 0<br>
&#9;&#9;w = 1<br>
&#9;&#9;return Motor2(x, y, z, w)<br>
<br>
&#9;def __mul__(self, other):<br>
&#9;&#9;q = self<br>
&#9;&#9;p = other<br>
&#9;&#9;return Motor2(<br>
&#9;&#9;&#9;q.w*p.x + q.x*p.w - q.z*p.y + q.y*p.z,<br>
&#9;&#9;&#9;q.w*p.y + q.y*p.w - q.x*p.z + q.z*p.x,<br>
&#9;&#9;&#9;q.w*p.z + q.z*p.w,<br>
&#9;&#9;&#9;q.w*p.w - q.z*p.z<br>
&#9;&#9;)<br>
<br>
&#9;def mul_screw(self, scr):<br>
&#9;&#9;return self * Motor2.from_screw_naive(scr)<br>
<br>
&#9;def __add__(self, other):<br>
&#9;&#9;return Motor2(self.x+other.x, self.y+other.y, self.z+other.z, self.w+other.w)<br>
<br>
&#9;def mul_scalar(self, s):<br>
&#9;&#9;return Motor2(self.x*s, self.y*s, self.z*s, self.w*s)<br>
<br>
&#9;def transform_point(self, p):<br>
&#9;&#9;q = self<br>
&#9;&#9;return Point2(<br>
&#9;&#9;&#9;(q.w**2 - q.z**2)*p.x - 2*q.w*q.z *<br>
&#9;&#9;&#9;p.y + (2*q.w*q.x - 2*q.z*q.y)*p.z,<br>
&#9;&#9;&#9;(q.w**2 - q.z**2)*p.y + 2*q.w*q.z *<br>
&#9;&#9;&#9;p.x + (2*q.w*q.y + 2*q.z*q.x)*p.z,<br>
&#9;&#9;&#9;(q.w**2 + q.z**2)*p.z<br>
&#9;&#9;)<br>
<br>
&#9;def rotation_matrix(self):<br>
&#9;&#9;angle = self.angle()<br>
&#9;&#9;s = math.sin(angle)<br>
&#9;&#9;c = math.cos(angle)<br>
&#9;&#9;arr = numpy.array([<br>
&#9;&#9;&#9;[1, 0, 0],<br>
&#9;&#9;&#9;[0, c, -s],<br>
&#9;&#9;&#9;[0, s, c],<br>
&#9;&#9;])<br>
&#9;&#9;return arr<br>
<br>
&#9;def transform(self, o):<br>
&#9;&#9;if isinstance(o, Point2):<br>
&#9;&#9;&#9;return self.transform_point(o)<br>
<br>
&#9;def __repr__(self):<br>
&#9;&#9;return &quot;Motor(%s, %s, %s, %s)&quot; % (self.x, self.y, self.z, self.w)<br>
<br>
&#9;def __str__(self):<br>
&#9;&#9;return repr(self)<br>
<br>
&#9;def factorize_rotation_angle(self):<br>
&#9;&#9;return math.atan2(self.z, self.w) * 2<br>
<br>
&#9;def angle(self):<br>
&#9;&#9;return self.factorize_rotation_angle()<br>
<br>
&#9;def factorize_rotation(self):<br>
&#9;&#9;return Motor2(0, 0, self.z, self.w)<br>
<br>
&#9;def reverse(self):<br>
&#9;&#9;return Motor2(-self.x, -self.y, -self.z, self.w)<br>
<br>
&#9;def inverse(self):<br>
&#9;&#9;rotation = self.factorize_rotation()<br>
&#9;&#9;translation = self.factorize_translation()<br>
&#9;&#9;return rotation.reverse() * translation.reverse()<br>
<br>
&#9;def factorize_translation(self):<br>
&#9;&#9;q = self<br>
&#9;&#9;return Motor2(<br>
&#9;&#9;&#9;q.w*q.x - q.z*q.y,<br>
&#9;&#9;&#9;q.w*q.y + q.z*q.x,<br>
&#9;&#9;&#9;0,<br>
&#9;&#9;&#9;1<br>
&#9;&#9;)<br>
<br>
&#9;def factorize_translation_point(self):<br>
&#9;&#9;#probe = Point2(0,0)<br>
&#9;&#9;#r = self.transform_point(probe)<br>
&#9;&#9;# return Motor(r.x/2, r.y/2, 0, 1)<br>
&#9;&#9;q = self<br>
&#9;&#9;return Point2(<br>
&#9;&#9;&#9;q.w*q.x - q.z*q.y,<br>
&#9;&#9;&#9;q.w*q.y + q.z*q.x,<br>
&#9;&#9;&#9;1<br>
&#9;&#9;)<br>
<br>
&#9;def factorize_translation_vector(self):<br>
&#9;&#9;ft = self.factorize_translation()<br>
&#9;&#9;return numpy.array([ft.x*2, ft.y*2])<br>
<br>
&#9;def factorize_parameters(self):<br>
&#9;&#9;t = self.factorize_translation()<br>
&#9;&#9;angle = self.factorize_rotation_angle()<br>
&#9;&#9;x = t.x * 2<br>
&#9;&#9;y = t.y * 2<br>
&#9;&#9;return (angle, (x, y))<br>
<br>
&#9;def rotate_nparray(self, a):<br>
&#9;&#9;angle = self.factorize_rotation_angle()<br>
&#9;&#9;s = math.sin(angle)<br>
&#9;&#9;c = math.cos(angle)<br>
&#9;&#9;return numpy.array([<br>
&#9;&#9;&#9;c*a[0] - s*a[1],<br>
&#9;&#9;&#9;s*a[0] + c*a[1]<br>
&#9;&#9;])<br>
<br>
&#9;def average_with(self, other):<br>
&#9;&#9;ft = self.factorize_translation_vector()<br>
&#9;&#9;ft2 = other.factorize_translation_vector()<br>
&#9;&#9;ft_avg = (ft + ft2) / 2<br>
&#9;&#9;fr = self.factorize_rotation_angle()<br>
&#9;&#9;fr2 = other.factorize_rotation_angle()<br>
&#9;&#9;fr_avg = (fr + fr2) / 2<br>
&#9;&#9;return Motor2.translation(ft_avg[0], ft_avg[1]) * Motor2.rotation(fr_avg)<br>
<br>
<br>
&#9;def rotate_nparray_inverse(self, a):<br>
&#9;&#9;angle = self.factorize_rotation_angle()<br>
&#9;&#9;s = math.sin(angle)<br>
&#9;&#9;c = math.cos(angle)<br>
&#9;&#9;return numpy.array([<br>
&#9;&#9;&#9;c*a[0] + s*a[1],<br>
&#9;&#9;&#9;-s*a[0] + c*a[1]<br>
&#9;&#9;])<br>
<br>
&#9;def __eq__(self, oth):<br>
&#9;&#9;return (<br>
&#9;&#9;&#9;self.x == oth.x and<br>
&#9;&#9;&#9;self.y == oth.y and<br>
&#9;&#9;&#9;self.z == oth.z and<br>
&#9;&#9;&#9;self.w == oth.w<br>
&#9;&#9;)<br>
<br>
&#9;def __sub__(self, oth):<br>
&#9;&#9;return Motor2(<br>
&#9;&#9;&#9;self.x - oth.x,<br>
&#9;&#9;&#9;self.y - oth.y,<br>
&#9;&#9;&#9;self.z - oth.z,<br>
&#9;&#9;&#9;self.w - oth.w<br>
&#9;&#9;)<br>
<br>
&#9;def __truediv__(self, s):<br>
&#9;&#9;return Motor2(<br>
&#9;&#9;&#9;self.x / s,<br>
&#9;&#9;&#9;self.y / s,<br>
&#9;&#9;&#9;self.z / s,<br>
&#9;&#9;&#9;self.w / s<br>
&#9;&#9;)<br>
<br>
&#9;def is_zero_equal(self, eps=1e-8):<br>
&#9;&#9;a = numpy.array([self.x, self.y, self.z, self.w])<br>
&#9;&#9;return numpy.linalg.norm(a) &lt; eps<br>
<br>
&#9;def splash_to_screw(self):<br>
&#9;&#9;return Screw2(<br>
&#9;&#9;&#9;m=self.z,<br>
&#9;&#9;&#9;v=[self.x,<br>
&#9;&#9;&#9;self.y]<br>
&#9;&#9;)<br>
<br>
&#9;@staticmethod<br>
&#9;def from_screw(scr):<br>
&#9;&#9;return Motor2.translation(*scr.lin()) * Motor2.rotation(scr.ang())<br>
<br>
&#9;@staticmethod<br>
&#9;def from_screw_naive(scr):<br>
&#9;&#9;return Motor2(<br>
&#9;&#9;&#9;scr.lin()[0],<br>
&#9;&#9;&#9;scr.lin()[1],<br>
&#9;&#9;&#9;scr.ang(),<br>
&#9;&#9;&#9;0<br>
&#9;&#9;)<br>
<!-- END SCAT CODE -->
</body>
</html>
