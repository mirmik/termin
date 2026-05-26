import termin.ga201.point as point
import termin.ga201.join as join


class Line2:
    def __init__(self, x, y, z):
        n = (x*x + y*y)**0.5
        self.x = x / n
        self.y = y / n
        self.z = z / n
        
    def __str__(self):
        return str((self.x, self.y, self.z))

    def __repr__(self):
        return str(self)

    def bulk_norm(self):
        return (self.x*self.x + self.y*self.y)**0.5

    def parameter_point(self, t):
        n = self.bulk_norm()
        dir_y = self.x / n
        dir_x = -self.y / n
        origin = point.origin()
        c = join.projection_point_line(origin, self).unitized()
        return point.Point2(
            c.x + dir_x * t,
            c.y + dir_y * t
        )

    def unitized(self):
        x, y = self.x, self.y
        n = (x*x + y*y)**0.5
        return Line2(self.x/n, self.y/n, self.z/n)