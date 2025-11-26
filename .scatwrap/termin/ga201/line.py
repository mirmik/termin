<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ga201/line.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import termin.ga201.point as point<br>
import termin.ga201.join as join<br>
<br>
<br>
class Line2:<br>
    def __init__(self, x, y, z):<br>
        n = (x*x + y*y)**0.5<br>
        self.x = x / n<br>
        self.y = y / n<br>
        self.z = z / n<br>
        <br>
    def __str__(self):<br>
        return str((self.x, self.y, self.z))<br>
<br>
    def __repr__(self):<br>
        return str(self)<br>
<br>
    def bulk_norm(self):<br>
        return (self.x*self.x + self.y*self.y)**0.5<br>
<br>
    def parameter_point(self, t):<br>
        n = self.bulk_norm()<br>
        dir_y = self.x / n<br>
        dir_x = -self.y / n<br>
        origin = point.origin()<br>
        c = join.projection_point_line(origin, self).unitized()<br>
        return point.Point2(<br>
            c.x + dir_x * t,<br>
            c.y + dir_y * t<br>
        )<br>
<br>
    def unitized(self):<br>
        x, y = self.x, self.y<br>
        n = (x*x + y*y)**0.5<br>
        return Line2(self.x/n, self.y/n, self.z/n)<br>
<!-- END SCAT CODE -->
</body>
</html>
