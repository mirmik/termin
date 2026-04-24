
import math
from termin.ga201.point import Point2
from termin.ga201.screw import Screw2
import numpy


class Motor2:
    def __init__(self, x=0, y=0, z=0, w=1):
        self.x = x
        self.y = y
        self.z = z
        self.w = w

    def self_unitize(self):
        l = self.z * self.z + self.w * self.w
        n = math.sqrt(l)
        return Motor2(self.x / n,
                      self.y / n,
                      self.z / n,
                      self.w / n)

    def log(self):
        angle = self.factorize_rotation_angle()
        translation = self.factorize_translation_vector()
        return Screw2(angle, translation)

    @staticmethod
    def rotation(rads):
        z = math.sin(rads/2)
        w = math.cos(rads/2)
        return Motor2(0, 0, z, w)

    @staticmethod
    def translation(x, y):
        x = x/2
        y = y/2
        z = 0
        w = 1
        return Motor2(x, y, z, w)

    def __mul__(self, other):
        q = self
        p = other
        return Motor2(
            q.w*p.x + q.x*p.w - q.z*p.y + q.y*p.z,
            q.w*p.y + q.y*p.w - q.x*p.z + q.z*p.x,
            q.w*p.z + q.z*p.w,
            q.w*p.w - q.z*p.z
        )

    def mul_screw(self, scr):
        return self * Motor2.from_screw_naive(scr)

    def __add__(self, other):
        return Motor2(self.x+other.x, self.y+other.y, self.z+other.z, self.w+other.w)

    def mul_scalar(self, s):
        return Motor2(self.x*s, self.y*s, self.z*s, self.w*s)

    def transform_point(self, p):
        q = self
        return Point2(
            (q.w**2 - q.z**2)*p.x - 2*q.w*q.z *
            p.y + (2*q.w*q.x - 2*q.z*q.y)*p.z,
            (q.w**2 - q.z**2)*p.y + 2*q.w*q.z *
            p.x + (2*q.w*q.y + 2*q.z*q.x)*p.z,
            (q.w**2 + q.z**2)*p.z
        )

    def rotation_matrix(self):
        angle = self.angle()
        s = math.sin(angle)
        c = math.cos(angle)
        arr = numpy.array([
            [1, 0, 0],
            [0, c, -s],
            [0, s, c],
        ])
        return arr

    def transform(self, o):
        if isinstance(o, Point2):
            return self.transform_point(o)

    def __repr__(self):
        return "Motor(%s, %s, %s, %s)" % (self.x, self.y, self.z, self.w)

    def __str__(self):
        return repr(self)

    def factorize_rotation_angle(self):
        return math.atan2(self.z, self.w) * 2

    def angle(self):
        return self.factorize_rotation_angle()

    def factorize_rotation(self):
        return Motor2(0, 0, self.z, self.w)

    def reverse(self):
        return Motor2(-self.x, -self.y, -self.z, self.w)

    def inverse(self):
        rotation = self.factorize_rotation()
        translation = self.factorize_translation()
        return rotation.reverse() * translation.reverse()

    def factorize_translation(self):
        q = self
        return Motor2(
            q.w*q.x - q.z*q.y,
            q.w*q.y + q.z*q.x,
            0,
            1
        )

    def factorize_translation_point(self):
        #probe = Point2(0,0)
        #r = self.transform_point(probe)
        # return Motor(r.x/2, r.y/2, 0, 1)
        q = self
        return Point2(
            q.w*q.x - q.z*q.y,
            q.w*q.y + q.z*q.x,
            1
        )

    def factorize_translation_vector(self):
        ft = self.factorize_translation()
        return numpy.array([ft.x*2, ft.y*2])

    def factorize_parameters(self):
        t = self.factorize_translation()
        angle = self.factorize_rotation_angle()
        x = t.x * 2
        y = t.y * 2
        return (angle, (x, y))

    def rotate_nparray(self, a):
        angle = self.factorize_rotation_angle()
        s = math.sin(angle)
        c = math.cos(angle)
        return numpy.array([
            c*a[0] - s*a[1],
            s*a[0] + c*a[1]
        ])

    def average_with(self, other):
        ft = self.factorize_translation_vector()
        ft2 = other.factorize_translation_vector()
        ft_avg = (ft + ft2) / 2
        fr = self.factorize_rotation_angle()
        fr2 = other.factorize_rotation_angle()
        fr_avg = (fr + fr2) / 2
        return Motor2.translation(ft_avg[0], ft_avg[1]) * Motor2.rotation(fr_avg)


    def rotate_nparray_inverse(self, a):
        angle = self.factorize_rotation_angle()
        s = math.sin(angle)
        c = math.cos(angle)
        return numpy.array([
            c*a[0] + s*a[1],
            -s*a[0] + c*a[1]
        ])

    def __eq__(self, oth):
        return (
            self.x == oth.x and
            self.y == oth.y and
            self.z == oth.z and
            self.w == oth.w
        )

    def __sub__(self, oth):
        return Motor2(
            self.x - oth.x,
            self.y - oth.y,
            self.z - oth.z,
            self.w - oth.w
        )

    def __truediv__(self, s):
        return Motor2(
            self.x / s,
            self.y / s,
            self.z / s,
            self.w / s
        )

    def is_zero_equal(self, eps=1e-8):
        a = numpy.array([self.x, self.y, self.z, self.w])
        return numpy.linalg.norm(a) < eps

    def splash_to_screw(self):
        return Screw2(
            m=self.z,
            v=[self.x,
            self.y]
        )

    @staticmethod
    def from_screw(scr):
        return Motor2.translation(*scr.lin()) * Motor2.rotation(scr.ang())

    @staticmethod
    def from_screw_naive(scr):
        return Motor2(
            scr.lin()[0],
            scr.lin()[1],
            scr.ang(),
            0
        )