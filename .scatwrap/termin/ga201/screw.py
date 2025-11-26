<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ga201/screw.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env python3<br>
<br>
import math<br>
import numpy<br>
<br>
<br>
class Screw2:<br>
&#9;def __init__(self, m=0, v=numpy.array([0, 0])):<br>
&#9;&#9;self._m = m<br>
&#9;&#9;self._v = numpy.array(v)<br>
<br>
&#9;&#9;if not isinstance(self._v, numpy.ndarray) and self._v.shape != (2,):<br>
&#9;&#9;&#9;raise Exception(&quot;Vector must be numpy.ndarray&quot;)<br>
<br>
&#9;&#9;if not isinstance(self._m, (int, float)):<br>
&#9;&#9;&#9;raise Exception(&quot;Moment must be int or float&quot;)<br>
<br>
&#9;def lin(self):<br>
&#9;&#9;return self._v<br>
<br>
&#9;def ang(self):<br>
&#9;&#9;return self._m<br>
<br>
&#9;def vector(self):<br>
&#9;&#9;return self._v<br>
<br>
&#9;def moment(self):<br>
&#9;&#9;return self._m<br>
<br>
&#9;def norm(self):<br>
&#9;&#9;return math.sqrt(self._m * self._m + self._v.dot(self._v))<br>
<br>
&#9;def set_vector(self, v):<br>
&#9;&#9;self._v = v<br>
<br>
&#9;def set_moment(self, m):<br>
&#9;&#9;self._m = m<br>
<br>
&#9;def as_array(self):<br>
&#9;&#9;return numpy.array([self._m, *self._v])<br>
<br>
&#9;def kinematic_carry(self, motor):<br>
&#9;&#9;a = motor.mul_screw(self)<br>
&#9;&#9;a = a * motor.reverse()<br>
&#9;&#9;return a.splash_to_screw()<br>
<br>
&#9;def carry(self, motor):<br>
&#9;&#9;&quot;&quot;&quot; carry(S,P) = PSP* &quot;&quot;&quot;<br>
&#9;&#9;return self.kinematic_carry(motor)<br>
<br>
&#9;def inverse_kinematic_carry (self, motor):<br>
&#9;&#9;a = motor.reverse().mul_screw(self)<br>
&#9;&#9;a = a * motor<br>
&#9;&#9;return a.splash_to_screw()<br>
&#9;<br>
&#9;def inverse_carry(self, motor):<br>
&#9;&#9;&quot;&quot;&quot; inverse_carry(S,P) = P*SP &quot;&quot;&quot;<br>
&#9;&#9;return self.inverse_kinematic_carry(motor)<br>
&#9;&#9;<br>
<br>
&#9;def fulldot(self, other):<br>
&#9;&#9;return self._m * other._m + self._v.dot(other._v)<br>
<br>
&#9;def force_carry(self, motor):<br>
&#9;&#9;angle = motor.factorize_rotation_angle()<br>
&#9;&#9;translation = motor.factorize_translation_vector()<br>
&#9;&#9;rotated_scr = self.rotate_by_angle(angle)<br>
&#9;&#9;m = rotated_scr.moment()<br>
&#9;&#9;v = rotated_scr.vector()<br>
&#9;&#9;b = translation<br>
&#9;&#9;a = -m<br>
<br>
&#9;&#9;print(&quot;TODO: force carry&quot;)<br>
&#9;&#9;new_m = m<br>
&#9;&#9;new_v = v<br>
&#9;&#9;ret = Screw2(m=new_m, v=new_v)<br>
&#9;&#9;return ret<br>
<br>
&#9;def inverted_kinematic_carry(self, motor):<br>
&#9;&#9;return self.inverse_kinematic_carry(motor)<br>
<br>
&#9;def kinematic_carry_vec(self, translation):<br>
&#9;&#9;m = self._m<br>
&#9;&#9;v = self._v<br>
&#9;&#9;b = translation<br>
&#9;&#9;a = -m  # (w+v)'=w+v-w*t : из уравнения (v+w)'=(1+t/2)(v+w)(1-t/2)<br>
&#9;&#9;ret = Screw2(m=m, v=v + numpy.array([<br>
&#9;&#9;&#9;-a * b[1], a * b[0]<br>
&#9;&#9;]))<br>
&#9;&#9;return ret<br>
<br>
&#9;def rotate_by_angle(self, angle):<br>
&#9;&#9;m = self._m<br>
&#9;&#9;v = self._v<br>
&#9;&#9;s = math.sin(angle)<br>
&#9;&#9;c = math.cos(angle)<br>
&#9;&#9;return Screw2(m=m, v=numpy.array([<br>
&#9;&#9;&#9;c*v[0] - s*v[1],<br>
&#9;&#9;&#9;s*v[0] + c*v[1]<br>
&#9;&#9;]))<br>
<br>
&#9;def rotate_by(self, motor):<br>
&#9;&#9;return self.rotate_by_angle(motor.angle())<br>
<br>
&#9;def inverse_rotate_by(self, motor):<br>
&#9;&#9;return self.rotate_by_angle(-motor.angle())<br>
<br>
&#9;def __str__(self):<br>
&#9;&#9;return &quot;Screw2(%s, %s)&quot; % (self._m, self._v)<br>
<br>
&#9;def __mul__(self, s):<br>
&#9;&#9;return Screw2(v=self._v*s, m=self._m*s)<br>
<br>
&#9;def __truediv__(self, s):<br>
&#9;&#9;return Screw2(v=self._v/s, m=self._m/s)<br>
<br>
&#9;def __add__(self, oth):<br>
&#9;&#9;return Screw2(v=self._v+oth._v, m=self._m+oth._m)<br>
<br>
&#9;def __neg__(self):<br>
&#9;&#9;return Screw2(v=-self._v, m=-self._m)<br>
<br>
&#9;def __sub__(self, oth):<br>
&#9;&#9;return Screw2(v=self._v-oth._v, m=self._m-oth._m)<br>
<br>
&#9;def toarray(self):<br>
&#9;&#9;return numpy.array([self.moment(), *self.vector()])<br>
<br>
&#9;@staticmethod<br>
&#9;def from_array(arr):<br>
&#9;&#9;return Screw2(m=arr[0], v=arr[1:])<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
&#9;from termin.ga201.motor import Motor2<br>
&#9;# scr = Screw2(m=0, v=[1, 0])<br>
&#9;# mot = Motor2.rotation(math.pi/2)<br>
&#9;# print(scr.kinematic_carry(mot))<br>
&#9;# print(scr.inverted_kinematic_carry(mot))<br>
<br>
&#9;scr = Screw2(m=1, v=[0, 0])<br>
&#9;mot = Motor2.translation(1, 0)<br>
&#9;print(scr.kinematic_carry(mot))<br>
&#9;print(scr.inverted_kinematic_carry(mot))<br>
<br>
&#9;# scr = Screw2(m=0, v=[1, 0])<br>
&#9;# print(scr.rotate_by_angle(math.pi/2))<br>
<br>
&#9;# scr = Screw2(m=1, v=[0, 0])<br>
&#9;# print(scr.rotate_by_angle(math.pi/2))<br>
<!-- END SCAT CODE -->
</body>
</html>
