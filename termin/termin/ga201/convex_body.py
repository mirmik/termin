import termin.ga201.join as join
import termin.ga201.point as point
import numpy as np
from itertools import combinations
from scipy.spatial import ConvexHull

class ConvexBody2:
    def __init__(self, planes, inverted = False):
        self.planes = planes
        self.linear_formes_by_grades = [0] * (self.max_grade()) 
        self.find_linear_formes()
        self.inverted = inverted

    @staticmethod
    def from_points(points):
        cpnts = [(p.x, p.y) for p in [p.unitized() for p in points]]
        c = ConvexHull(cpnts)    
        planes = []
        for i in range(len(c.vertices)-1):
            planes.append(join.join_point_point(points[i], points[i+1]))
        planes.append(join.join_point_point(points[len(c.vertices)-1], points[0]))
        body = ConvexBody2(planes)
        return body

    def max_grade(self):
        return 2

    def meet_of_hyperplanes_combination(self, planes):
        result = planes[0]
        for i in range(1, len(planes)):
            result = join.meet(result, planes[i])
        return result

    def internal_vertices(self, vertices):
        int_vertices = []
        for vertex in vertices:
            is_internal = True
            for plane in self.planes:
                is_internal = self.is_internal_point(vertex)
                if not is_internal:
                    break
            if is_internal:
                int_vertices.append(vertex)        
        return int_vertices

    def drop_infinite_points(self, vertices):
        non_infinite_points = []
        for vertex in vertices:
            if vertex.is_infinite():
                continue
            non_infinite_points.append(vertex)
        return non_infinite_points

    def meet_of_hyperplanes(self):
        # get list of all vertices of convex body
        # by list of planes
        # planes - list of planes

        # get list of all combination of planes by max_grade elements
        cmbs = [c for c in combinations(self.planes, self.max_grade())]
        vertices = []

        for cmb in cmbs:
            # get all vertices of cmb
            # and add them to vertices list
            pnt = self.meet_of_hyperplanes_combination(cmb)
            vertices.append(pnt.unitized())

        non_infinite_points = self.drop_infinite_points(vertices)
        int_vertices = self.internal_vertices(non_infinite_points)

        return int_vertices

    def find_linear_formes(self):
        # get list of all combination of planes by max_grade elements
        self.linear_formes_by_grades[self.max_grade() - 1] = self.planes
        vertices = self.meet_of_hyperplanes()
        self.linear_formes_by_grades[0] = vertices

        #TODO: middle grades

    def count_of_vertices(self):
        return len(self.linear_formes_by_grades[0])

    def count_of_hyperplanes(self):
        return len(self.planes)
        
    def vertices(self):
        return self.linear_formes_by_grades[0]

    def hyperplanes(self):
        return self.linear_formes_by_grades[self.max_grade() - 1]

    def is_internal_point(self, point):
        for plane in self.planes:
            if join.oriented_distance(point, plane).to_float() > 1e-8:
                return False
        return True
    
    def point_projection(self, point):
        candidates = []
        for grade in range(self.max_grade()-1, -1, -1):
            for linear_form in self.linear_formes_by_grades[grade]:
                proj = join.point_projection(point, linear_form)
                if self.is_internal_point(proj):
                    candidates.append(proj)

        distances = [join.distance_point_point(point, candidate).to_float() for candidate in candidates]
        min_distance_index = np.argmin(distances)
        return candidates[min_distance_index]


class ConvexWorld2:
    def __init__(self, bodies):
        self.bodies = bodies

    def point_projection(self, point):
        candidates = []
        for body in self.bodies:
            candidates.append(body.point_projection(point))

        distances = [join.distance_point_point(point, candidate).to_float() for candidate in candidates]
        min_distance_index = np.argmin(distances)
        return candidates[min_distance_index]