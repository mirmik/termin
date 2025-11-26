<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ga201/convex_body.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import termin.ga201.join as join<br>
import termin.ga201.point as point<br>
import numpy as np<br>
from itertools import combinations<br>
from scipy.spatial import ConvexHull<br>
<br>
class ConvexBody2:<br>
&#9;def __init__(self, planes, inverted = False):<br>
&#9;&#9;self.planes = planes<br>
&#9;&#9;self.linear_formes_by_grades = [0] * (self.max_grade()) <br>
&#9;&#9;self.find_linear_formes()<br>
&#9;&#9;self.inverted = inverted<br>
<br>
&#9;@staticmethod<br>
&#9;def from_points(points):<br>
&#9;&#9;cpnts = [(p.x, p.y) for p in [p.unitized() for p in points]]<br>
&#9;&#9;c = ConvexHull(cpnts)    <br>
&#9;&#9;planes = []<br>
&#9;&#9;for i in range(len(c.vertices)-1):<br>
&#9;&#9;&#9;planes.append(join.join_point_point(points[i], points[i+1]))<br>
&#9;&#9;planes.append(join.join_point_point(points[len(c.vertices)-1], points[0]))<br>
&#9;&#9;body = ConvexBody2(planes)<br>
&#9;&#9;return body<br>
<br>
&#9;def max_grade(self):<br>
&#9;&#9;return 2<br>
<br>
&#9;def meet_of_hyperplanes_combination(self, planes):<br>
&#9;&#9;result = planes[0]<br>
&#9;&#9;for i in range(1, len(planes)):<br>
&#9;&#9;&#9;result = join.meet(result, planes[i])<br>
&#9;&#9;return result<br>
<br>
&#9;def internal_vertices(self, vertices):<br>
&#9;&#9;int_vertices = []<br>
&#9;&#9;for vertex in vertices:<br>
&#9;&#9;&#9;is_internal = True<br>
&#9;&#9;&#9;for plane in self.planes:<br>
&#9;&#9;&#9;&#9;is_internal = self.is_internal_point(vertex)<br>
&#9;&#9;&#9;&#9;if not is_internal:<br>
&#9;&#9;&#9;&#9;&#9;break<br>
&#9;&#9;&#9;if is_internal:<br>
&#9;&#9;&#9;&#9;int_vertices.append(vertex)        <br>
&#9;&#9;return int_vertices<br>
<br>
&#9;def drop_infinite_points(self, vertices):<br>
&#9;&#9;non_infinite_points = []<br>
&#9;&#9;for vertex in vertices:<br>
&#9;&#9;&#9;if vertex.is_infinite():<br>
&#9;&#9;&#9;&#9;continue<br>
&#9;&#9;&#9;non_infinite_points.append(vertex)<br>
&#9;&#9;return non_infinite_points<br>
<br>
&#9;def meet_of_hyperplanes(self):<br>
&#9;&#9;# get list of all vertices of convex body<br>
&#9;&#9;# by list of planes<br>
&#9;&#9;# planes - list of planes<br>
<br>
&#9;&#9;# get list of all combination of planes by max_grade elements<br>
&#9;&#9;cmbs = [c for c in combinations(self.planes, self.max_grade())]<br>
&#9;&#9;vertices = []<br>
<br>
&#9;&#9;for cmb in cmbs:<br>
&#9;&#9;&#9;# get all vertices of cmb<br>
&#9;&#9;&#9;# and add them to vertices list<br>
&#9;&#9;&#9;pnt = self.meet_of_hyperplanes_combination(cmb)<br>
&#9;&#9;&#9;vertices.append(pnt.unitized())<br>
<br>
&#9;&#9;non_infinite_points = self.drop_infinite_points(vertices)<br>
&#9;&#9;int_vertices = self.internal_vertices(non_infinite_points)<br>
<br>
&#9;&#9;return int_vertices<br>
<br>
&#9;def find_linear_formes(self):<br>
&#9;&#9;# get list of all combination of planes by max_grade elements<br>
&#9;&#9;self.linear_formes_by_grades[self.max_grade() - 1] = self.planes<br>
&#9;&#9;vertices = self.meet_of_hyperplanes()<br>
&#9;&#9;self.linear_formes_by_grades[0] = vertices<br>
<br>
&#9;&#9;#TODO: middle grades<br>
<br>
&#9;def count_of_vertices(self):<br>
&#9;&#9;return len(self.linear_formes_by_grades[0])<br>
<br>
&#9;def count_of_hyperplanes(self):<br>
&#9;&#9;return len(self.planes)<br>
&#9;&#9;<br>
&#9;def vertices(self):<br>
&#9;&#9;return self.linear_formes_by_grades[0]<br>
<br>
&#9;def hyperplanes(self):<br>
&#9;&#9;return self.linear_formes_by_grades[self.max_grade() - 1]<br>
<br>
&#9;def is_internal_point(self, point):<br>
&#9;&#9;for plane in self.planes:<br>
&#9;&#9;&#9;if join.oriented_distance(point, plane).to_float() &gt; 1e-8:<br>
&#9;&#9;&#9;&#9;return False<br>
&#9;&#9;return True<br>
&#9;<br>
&#9;def point_projection(self, point):<br>
&#9;&#9;candidates = []<br>
&#9;&#9;for grade in range(self.max_grade()-1, -1, -1):<br>
&#9;&#9;&#9;for linear_form in self.linear_formes_by_grades[grade]:<br>
&#9;&#9;&#9;&#9;proj = join.point_projection(point, linear_form)<br>
&#9;&#9;&#9;&#9;if self.is_internal_point(proj):<br>
&#9;&#9;&#9;&#9;&#9;candidates.append(proj)<br>
<br>
&#9;&#9;distances = [join.distance_point_point(point, candidate).to_float() for candidate in candidates]<br>
&#9;&#9;min_distance_index = np.argmin(distances)<br>
&#9;&#9;return candidates[min_distance_index]<br>
<br>
<br>
class ConvexWorld2:<br>
&#9;def __init__(self, bodies):<br>
&#9;&#9;self.bodies = bodies<br>
<br>
&#9;def point_projection(self, point):<br>
&#9;&#9;candidates = []<br>
&#9;&#9;for body in self.bodies:<br>
&#9;&#9;&#9;candidates.append(body.point_projection(point))<br>
<br>
&#9;&#9;distances = [join.distance_point_point(point, candidate).to_float() for candidate in candidates]<br>
&#9;&#9;min_distance_index = np.argmin(distances)<br>
&#9;&#9;return candidates[min_distance_index]<br>
<!-- END SCAT CODE -->
</body>
</html>
