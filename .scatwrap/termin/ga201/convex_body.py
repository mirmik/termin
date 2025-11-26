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
    def __init__(self, planes, inverted = False):<br>
        self.planes = planes<br>
        self.linear_formes_by_grades = [0] * (self.max_grade()) <br>
        self.find_linear_formes()<br>
        self.inverted = inverted<br>
<br>
    @staticmethod<br>
    def from_points(points):<br>
        cpnts = [(p.x, p.y) for p in [p.unitized() for p in points]]<br>
        c = ConvexHull(cpnts)    <br>
        planes = []<br>
        for i in range(len(c.vertices)-1):<br>
            planes.append(join.join_point_point(points[i], points[i+1]))<br>
        planes.append(join.join_point_point(points[len(c.vertices)-1], points[0]))<br>
        body = ConvexBody2(planes)<br>
        return body<br>
<br>
    def max_grade(self):<br>
        return 2<br>
<br>
    def meet_of_hyperplanes_combination(self, planes):<br>
        result = planes[0]<br>
        for i in range(1, len(planes)):<br>
            result = join.meet(result, planes[i])<br>
        return result<br>
<br>
    def internal_vertices(self, vertices):<br>
        int_vertices = []<br>
        for vertex in vertices:<br>
            is_internal = True<br>
            for plane in self.planes:<br>
                is_internal = self.is_internal_point(vertex)<br>
                if not is_internal:<br>
                    break<br>
            if is_internal:<br>
                int_vertices.append(vertex)        <br>
        return int_vertices<br>
<br>
    def drop_infinite_points(self, vertices):<br>
        non_infinite_points = []<br>
        for vertex in vertices:<br>
            if vertex.is_infinite():<br>
                continue<br>
            non_infinite_points.append(vertex)<br>
        return non_infinite_points<br>
<br>
    def meet_of_hyperplanes(self):<br>
        # get list of all vertices of convex body<br>
        # by list of planes<br>
        # planes - list of planes<br>
<br>
        # get list of all combination of planes by max_grade elements<br>
        cmbs = [c for c in combinations(self.planes, self.max_grade())]<br>
        vertices = []<br>
<br>
        for cmb in cmbs:<br>
            # get all vertices of cmb<br>
            # and add them to vertices list<br>
            pnt = self.meet_of_hyperplanes_combination(cmb)<br>
            vertices.append(pnt.unitized())<br>
<br>
        non_infinite_points = self.drop_infinite_points(vertices)<br>
        int_vertices = self.internal_vertices(non_infinite_points)<br>
<br>
        return int_vertices<br>
<br>
    def find_linear_formes(self):<br>
        # get list of all combination of planes by max_grade elements<br>
        self.linear_formes_by_grades[self.max_grade() - 1] = self.planes<br>
        vertices = self.meet_of_hyperplanes()<br>
        self.linear_formes_by_grades[0] = vertices<br>
<br>
        #TODO: middle grades<br>
<br>
    def count_of_vertices(self):<br>
        return len(self.linear_formes_by_grades[0])<br>
<br>
    def count_of_hyperplanes(self):<br>
        return len(self.planes)<br>
        <br>
    def vertices(self):<br>
        return self.linear_formes_by_grades[0]<br>
<br>
    def hyperplanes(self):<br>
        return self.linear_formes_by_grades[self.max_grade() - 1]<br>
<br>
    def is_internal_point(self, point):<br>
        for plane in self.planes:<br>
            if join.oriented_distance(point, plane).to_float() &gt; 1e-8:<br>
                return False<br>
        return True<br>
    <br>
    def point_projection(self, point):<br>
        candidates = []<br>
        for grade in range(self.max_grade()-1, -1, -1):<br>
            for linear_form in self.linear_formes_by_grades[grade]:<br>
                proj = join.point_projection(point, linear_form)<br>
                if self.is_internal_point(proj):<br>
                    candidates.append(proj)<br>
<br>
        distances = [join.distance_point_point(point, candidate).to_float() for candidate in candidates]<br>
        min_distance_index = np.argmin(distances)<br>
        return candidates[min_distance_index]<br>
<br>
<br>
class ConvexWorld2:<br>
    def __init__(self, bodies):<br>
        self.bodies = bodies<br>
<br>
    def point_projection(self, point):<br>
        candidates = []<br>
        for body in self.bodies:<br>
            candidates.append(body.point_projection(point))<br>
<br>
        distances = [join.distance_point_point(point, candidate).to_float() for candidate in candidates]<br>
        min_distance_index = np.argmin(distances)<br>
        return candidates[min_distance_index]<br>
<!-- END SCAT CODE -->
</body>
</html>
