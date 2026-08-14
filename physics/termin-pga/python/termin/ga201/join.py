#!/usr/bin/env python3

from termin.ga201.point import Point2
from termin.ga201.line import Line2
from termin.ga201.magnitude import Magnitude
import math

def join_point_point(p, q):
    return Line2(
        p.y*q.z - q.y*p.z,
        q.x*p.z - p.x*q.z,
        p.x*q.y - q.x*p.y
    )

def projection_point_line(p, l):
    a = (l.x*l.x + l.y*l.y)
    b = (l.x*p.x + l.y*p.y + l.z*p.z)
    return Point2(
        a * p.x - b * l.x,
        a * p.y - b * l.y,
        a * p.z
    )

def point_projection(p, l):
    if isinstance(l, Point2):
        return l
    if isinstance(l, Line2):
        return projection_point_line(p, l)

def meet(l, k):
    return Point2(
        l.y*k.z - k.y*l.z,
        k.x*l.z - l.x*k.z,
        l.x*k.y - k.x*l.y
    )

def oriented_distance_point_line(p,l):
    return Magnitude(
        p.x*l.x + p.y*l.y + p.z*l.z, 
        p.z*math.sqrt(l.x*l.x + l.y*l.y))

def distance_point_point(p, q):
    return Magnitude(
        math.sqrt((q.x*p.z - p.x*q.z)**2 + (q.y*p.z - p.y*q.z)**2),
        abs(p.z*q.z)
    )

def oriented_distance(a, b):
    if isinstance(b, Line2):
        return oriented_distance_point_line(a, b)
    raise Exception("Oriented distance allowed only for hyperplanes")
    

def distance(p, l):
    return abs(oriented_distance(p, l))

if __name__ == "__main__":
    p = Point2(1, 1)
    q = Point2(1, 0)
    print(join_point_point(p, q))

    l = Line2(1, 1, -1)
    print(projection_point_line(Point2(1, 1), l))

