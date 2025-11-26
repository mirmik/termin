<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ga201/join.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env python3<br>
<br>
from termin.ga201.point import Point2<br>
from termin.ga201.line import Line2<br>
from termin.ga201.magnitude import Magnitude<br>
import math<br>
<br>
def join_point_point(p, q):<br>
    return Line2(<br>
        p.y*q.z - q.y*p.z,<br>
        q.x*p.z - p.x*q.z,<br>
        p.x*q.y - q.x*p.y<br>
    )<br>
<br>
def projection_point_line(p, l):<br>
    a = (l.x*l.x + l.y*l.y)<br>
    b = (l.x*p.x + l.y*p.y + l.z*p.z)<br>
    return Point2(<br>
        a * p.x - b * l.x,<br>
        a * p.y - b * l.y,<br>
        a * p.z<br>
    )<br>
<br>
def point_projection(p, l):<br>
    if isinstance(l, Point2):<br>
        return l<br>
    if isinstance(l, Line2):<br>
        return projection_point_line(p, l)<br>
<br>
def meet(l, k):<br>
    return Point2(<br>
        l.y*k.z - k.y*l.z,<br>
        k.x*l.z - l.x*k.z,<br>
        l.x*k.y - k.x*l.y<br>
    )<br>
<br>
def oriented_distance_point_line(p,l):<br>
    return Magnitude(<br>
        p.x*l.x + p.y*l.y + p.z*l.z, <br>
        p.z*math.sqrt(l.x*l.x + l.y*l.y))<br>
<br>
def distance_point_point(p, q):<br>
    return Magnitude(<br>
        math.sqrt((q.x*p.z - p.x*q.z)**2 + (q.y*p.z - p.y*q.z)**2),<br>
        abs(p.z*q.z)<br>
    )<br>
<br>
def oriented_distance(a, b):<br>
    if isinstance(b, Line2):<br>
        return oriented_distance_point_line(a, b)<br>
    raise Exception(&quot;Oriented distance allowed only for hyperplanes&quot;)<br>
    <br>
<br>
def distance(p, l):<br>
    return abs(oriented_distance(p, l))<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
    p = Point2(1, 1)<br>
    q = Point2(1, 0)<br>
    print(join_point_point(p, q))<br>
<br>
    l = Line2(1, 1, -1)<br>
    print(projection_point_line(Point2(1, 1), l))<br>
<br>
<!-- END SCAT CODE -->
</body>
</html>
