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
&#9;return Line2(<br>
&#9;&#9;p.y*q.z - q.y*p.z,<br>
&#9;&#9;q.x*p.z - p.x*q.z,<br>
&#9;&#9;p.x*q.y - q.x*p.y<br>
&#9;)<br>
<br>
def projection_point_line(p, l):<br>
&#9;a = (l.x*l.x + l.y*l.y)<br>
&#9;b = (l.x*p.x + l.y*p.y + l.z*p.z)<br>
&#9;return Point2(<br>
&#9;&#9;a * p.x - b * l.x,<br>
&#9;&#9;a * p.y - b * l.y,<br>
&#9;&#9;a * p.z<br>
&#9;)<br>
<br>
def point_projection(p, l):<br>
&#9;if isinstance(l, Point2):<br>
&#9;&#9;return l<br>
&#9;if isinstance(l, Line2):<br>
&#9;&#9;return projection_point_line(p, l)<br>
<br>
def meet(l, k):<br>
&#9;return Point2(<br>
&#9;&#9;l.y*k.z - k.y*l.z,<br>
&#9;&#9;k.x*l.z - l.x*k.z,<br>
&#9;&#9;l.x*k.y - k.x*l.y<br>
&#9;)<br>
<br>
def oriented_distance_point_line(p,l):<br>
&#9;return Magnitude(<br>
&#9;&#9;p.x*l.x + p.y*l.y + p.z*l.z, <br>
&#9;&#9;p.z*math.sqrt(l.x*l.x + l.y*l.y))<br>
<br>
def distance_point_point(p, q):<br>
&#9;return Magnitude(<br>
&#9;&#9;math.sqrt((q.x*p.z - p.x*q.z)**2 + (q.y*p.z - p.y*q.z)**2),<br>
&#9;&#9;abs(p.z*q.z)<br>
&#9;)<br>
<br>
def oriented_distance(a, b):<br>
&#9;if isinstance(b, Line2):<br>
&#9;&#9;return oriented_distance_point_line(a, b)<br>
&#9;raise Exception(&quot;Oriented distance allowed only for hyperplanes&quot;)<br>
&#9;<br>
<br>
def distance(p, l):<br>
&#9;return abs(oriented_distance(p, l))<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
&#9;p = Point2(1, 1)<br>
&#9;q = Point2(1, 0)<br>
&#9;print(join_point_point(p, q))<br>
<br>
&#9;l = Line2(1, 1, -1)<br>
&#9;print(projection_point_line(Point2(1, 1), l))<br>
<br>
<!-- END SCAT CODE -->
</body>
</html>
