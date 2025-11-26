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
    def __init__(self, x=0, y=0, z=0, w=1):<br>
        self.x = x<br>
        self.y = y<br>
        self.z = z<br>
        self.w = w<br>
<br>
    def self_unitize(self):<br>
        l = self.z * self.z + self.w * self.w<br>
        n = math.sqrt(l)<br>
        return Motor2(self.x / n,<br>
                      self.y / n,<br>
                      self.z / n,<br>
                      self.w / n)<br>
<br>
    def log(self):<br>
        angle = self.factorize_rotation_angle()<br>
        translation = self.factorize_translation_vector()<br>
        return Screw2(angle, translation)<br>
<br>
    @staticmethod<br>
    def rotation(rads):<br>
        z = math.sin(rads/2)<br>
        w = math.cos(rads/2)<br>
        return Motor2(0, 0, z, w)<br>
<br>
    @staticmethod<br>
    def translation(x, y):<br>
        x = x/2<br>
        y = y/2<br>
        z = 0<br>
        w = 1<br>
        return Motor2(x, y, z, w)<br>
<br>
    def __mul__(self, other):<br>
        q = self<br>
        p = other<br>
        return Motor2(<br>
            q.w*p.x + q.x*p.w - q.z*p.y + q.y*p.z,<br>
            q.w*p.y + q.y*p.w - q.x*p.z + q.z*p.x,<br>
            q.w*p.z + q.z*p.w,<br>
            q.w*p.w - q.z*p.z<br>
        )<br>
<br>
    def mul_screw(self, scr):<br>
        return self * Motor2.from_screw_naive(scr)<br>
<br>
    def __add__(self, other):<br>
        return Motor2(self.x+other.x, self.y+other.y, self.z+other.z, self.w+other.w)<br>
<br>
    def mul_scalar(self, s):<br>
        return Motor2(self.x*s, self.y*s, self.z*s, self.w*s)<br>
<br>
    def transform_point(self, p):<br>
        q = self<br>
        return Point2(<br>
            (q.w**2 - q.z**2)*p.x - 2*q.w*q.z *<br>
            p.y + (2*q.w*q.x - 2*q.z*q.y)*p.z,<br>
            (q.w**2 - q.z**2)*p.y + 2*q.w*q.z *<br>
            p.x + (2*q.w*q.y + 2*q.z*q.x)*p.z,<br>
            (q.w**2 + q.z**2)*p.z<br>
        )<br>
<br>
    def rotation_matrix(self):<br>
        angle = self.angle()<br>
        s = math.sin(angle)<br>
        c = math.cos(angle)<br>
        arr = numpy.array([<br>
            [1, 0, 0],<br>
            [0, c, -s],<br>
            [0, s, c],<br>
        ])<br>
        return arr<br>
<br>
    def transform(self, o):<br>
        if isinstance(o, Point2):<br>
            return self.transform_point(o)<br>
<br>
    def __repr__(self):<br>
        return &quot;Motor(%s, %s, %s, %s)&quot; % (self.x, self.y, self.z, self.w)<br>
<br>
    def __str__(self):<br>
        return repr(self)<br>
<br>
    def factorize_rotation_angle(self):<br>
        return math.atan2(self.z, self.w) * 2<br>
<br>
    def angle(self):<br>
        return self.factorize_rotation_angle()<br>
<br>
    def factorize_rotation(self):<br>
        return Motor2(0, 0, self.z, self.w)<br>
<br>
    def reverse(self):<br>
        return Motor2(-self.x, -self.y, -self.z, self.w)<br>
<br>
    def inverse(self):<br>
        rotation = self.factorize_rotation()<br>
        translation = self.factorize_translation()<br>
        return rotation.reverse() * translation.reverse()<br>
<br>
    def factorize_translation(self):<br>
        q = self<br>
        return Motor2(<br>
            q.w*q.x - q.z*q.y,<br>
            q.w*q.y + q.z*q.x,<br>
            0,<br>
            1<br>
        )<br>
<br>
    def factorize_translation_point(self):<br>
        #probe = Point2(0,0)<br>
        #r = self.transform_point(probe)<br>
        # return Motor(r.x/2, r.y/2, 0, 1)<br>
        q = self<br>
        return Point2(<br>
            q.w*q.x - q.z*q.y,<br>
            q.w*q.y + q.z*q.x,<br>
            1<br>
        )<br>
<br>
    def factorize_translation_vector(self):<br>
        ft = self.factorize_translation()<br>
        return numpy.array([ft.x*2, ft.y*2])<br>
<br>
    def factorize_parameters(self):<br>
        t = self.factorize_translation()<br>
        angle = self.factorize_rotation_angle()<br>
        x = t.x * 2<br>
        y = t.y * 2<br>
        return (angle, (x, y))<br>
<br>
    def rotate_nparray(self, a):<br>
        angle = self.factorize_rotation_angle()<br>
        s = math.sin(angle)<br>
        c = math.cos(angle)<br>
        return numpy.array([<br>
            c*a[0] - s*a[1],<br>
            s*a[0] + c*a[1]<br>
        ])<br>
<br>
    def average_with(self, other):<br>
        ft = self.factorize_translation_vector()<br>
        ft2 = other.factorize_translation_vector()<br>
        ft_avg = (ft + ft2) / 2<br>
        fr = self.factorize_rotation_angle()<br>
        fr2 = other.factorize_rotation_angle()<br>
        fr_avg = (fr + fr2) / 2<br>
        return Motor2.translation(ft_avg[0], ft_avg[1]) * Motor2.rotation(fr_avg)<br>
<br>
<br>
    def rotate_nparray_inverse(self, a):<br>
        angle = self.factorize_rotation_angle()<br>
        s = math.sin(angle)<br>
        c = math.cos(angle)<br>
        return numpy.array([<br>
            c*a[0] + s*a[1],<br>
            -s*a[0] + c*a[1]<br>
        ])<br>
<br>
    def __eq__(self, oth):<br>
        return (<br>
            self.x == oth.x and<br>
            self.y == oth.y and<br>
            self.z == oth.z and<br>
            self.w == oth.w<br>
        )<br>
<br>
    def __sub__(self, oth):<br>
        return Motor2(<br>
            self.x - oth.x,<br>
            self.y - oth.y,<br>
            self.z - oth.z,<br>
            self.w - oth.w<br>
        )<br>
<br>
    def __truediv__(self, s):<br>
        return Motor2(<br>
            self.x / s,<br>
            self.y / s,<br>
            self.z / s,<br>
            self.w / s<br>
        )<br>
<br>
    def is_zero_equal(self, eps=1e-8):<br>
        a = numpy.array([self.x, self.y, self.z, self.w])<br>
        return numpy.linalg.norm(a) &lt; eps<br>
<br>
    def splash_to_screw(self):<br>
        return Screw2(<br>
            m=self.z,<br>
            v=[self.x,<br>
            self.y]<br>
        )<br>
<br>
    @staticmethod<br>
    def from_screw(scr):<br>
        return Motor2.translation(*scr.lin()) * Motor2.rotation(scr.ang())<br>
<br>
    @staticmethod<br>
    def from_screw_naive(scr):<br>
        return Motor2(<br>
            scr.lin()[0],<br>
            scr.lin()[1],<br>
            scr.ang(),<br>
            0<br>
        )<br>
<!-- END SCAT CODE -->
</body>
</html>
