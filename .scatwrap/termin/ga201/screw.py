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
    def __init__(self, m=0, v=numpy.array([0, 0])):<br>
        self._m = m<br>
        self._v = numpy.array(v)<br>
<br>
        if not isinstance(self._v, numpy.ndarray) and self._v.shape != (2,):<br>
            raise Exception(&quot;Vector must be numpy.ndarray&quot;)<br>
<br>
        if not isinstance(self._m, (int, float)):<br>
            raise Exception(&quot;Moment must be int or float&quot;)<br>
<br>
    def lin(self):<br>
        return self._v<br>
<br>
    def ang(self):<br>
        return self._m<br>
<br>
    def vector(self):<br>
        return self._v<br>
<br>
    def moment(self):<br>
        return self._m<br>
<br>
    def norm(self):<br>
        return math.sqrt(self._m * self._m + self._v.dot(self._v))<br>
<br>
    def set_vector(self, v):<br>
        self._v = v<br>
<br>
    def set_moment(self, m):<br>
        self._m = m<br>
<br>
    def as_array(self):<br>
        return numpy.array([self._m, *self._v])<br>
<br>
    def kinematic_carry(self, motor):<br>
        a = motor.mul_screw(self)<br>
        a = a * motor.reverse()<br>
        return a.splash_to_screw()<br>
<br>
    def carry(self, motor):<br>
        &quot;&quot;&quot; carry(S,P) = PSP* &quot;&quot;&quot;<br>
        return self.kinematic_carry(motor)<br>
<br>
    def inverse_kinematic_carry (self, motor):<br>
        a = motor.reverse().mul_screw(self)<br>
        a = a * motor<br>
        return a.splash_to_screw()<br>
    <br>
    def inverse_carry(self, motor):<br>
        &quot;&quot;&quot; inverse_carry(S,P) = P*SP &quot;&quot;&quot;<br>
        return self.inverse_kinematic_carry(motor)<br>
        <br>
<br>
    def fulldot(self, other):<br>
        return self._m * other._m + self._v.dot(other._v)<br>
<br>
    def force_carry(self, motor):<br>
        angle = motor.factorize_rotation_angle()<br>
        translation = motor.factorize_translation_vector()<br>
        rotated_scr = self.rotate_by_angle(angle)<br>
        m = rotated_scr.moment()<br>
        v = rotated_scr.vector()<br>
        b = translation<br>
        a = -m<br>
<br>
        print(&quot;TODO: force carry&quot;)<br>
        new_m = m<br>
        new_v = v<br>
        ret = Screw2(m=new_m, v=new_v)<br>
        return ret<br>
<br>
    def inverted_kinematic_carry(self, motor):<br>
        return self.inverse_kinematic_carry(motor)<br>
<br>
    def kinematic_carry_vec(self, translation):<br>
        m = self._m<br>
        v = self._v<br>
        b = translation<br>
        a = -m  # (w+v)'=w+v-w*t : из уравнения (v+w)'=(1+t/2)(v+w)(1-t/2)<br>
        ret = Screw2(m=m, v=v + numpy.array([<br>
            -a * b[1], a * b[0]<br>
        ]))<br>
        return ret<br>
<br>
    def rotate_by_angle(self, angle):<br>
        m = self._m<br>
        v = self._v<br>
        s = math.sin(angle)<br>
        c = math.cos(angle)<br>
        return Screw2(m=m, v=numpy.array([<br>
            c*v[0] - s*v[1],<br>
            s*v[0] + c*v[1]<br>
        ]))<br>
<br>
    def rotate_by(self, motor):<br>
        return self.rotate_by_angle(motor.angle())<br>
<br>
    def inverse_rotate_by(self, motor):<br>
        return self.rotate_by_angle(-motor.angle())<br>
<br>
    def __str__(self):<br>
        return &quot;Screw2(%s, %s)&quot; % (self._m, self._v)<br>
<br>
    def __mul__(self, s):<br>
        return Screw2(v=self._v*s, m=self._m*s)<br>
<br>
    def __truediv__(self, s):<br>
        return Screw2(v=self._v/s, m=self._m/s)<br>
<br>
    def __add__(self, oth):<br>
        return Screw2(v=self._v+oth._v, m=self._m+oth._m)<br>
<br>
    def __neg__(self):<br>
        return Screw2(v=-self._v, m=-self._m)<br>
<br>
    def __sub__(self, oth):<br>
        return Screw2(v=self._v-oth._v, m=self._m-oth._m)<br>
<br>
    def toarray(self):<br>
        return numpy.array([self.moment(), *self.vector()])<br>
<br>
    @staticmethod<br>
    def from_array(arr):<br>
        return Screw2(m=arr[0], v=arr[1:])<br>
<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
    from termin.ga201.motor import Motor2<br>
    # scr = Screw2(m=0, v=[1, 0])<br>
    # mot = Motor2.rotation(math.pi/2)<br>
    # print(scr.kinematic_carry(mot))<br>
    # print(scr.inverted_kinematic_carry(mot))<br>
<br>
    scr = Screw2(m=1, v=[0, 0])<br>
    mot = Motor2.translation(1, 0)<br>
    print(scr.kinematic_carry(mot))<br>
    print(scr.inverted_kinematic_carry(mot))<br>
<br>
    # scr = Screw2(m=0, v=[1, 0])<br>
    # print(scr.rotate_by_angle(math.pi/2))<br>
<br>
    # scr = Screw2(m=1, v=[0, 0])<br>
    # print(scr.rotate_by_angle(math.pi/2))<br>
<!-- END SCAT CODE -->
</body>
</html>
