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
&#9;def __init__(self, x, y, z):<br>
&#9;&#9;n = (x*x + y*y)**0.5<br>
&#9;&#9;self.x = x / n<br>
&#9;&#9;self.y = y / n<br>
&#9;&#9;self.z = z / n<br>
&#9;&#9;<br>
&#9;def __str__(self):<br>
&#9;&#9;return str((self.x, self.y, self.z))<br>
<br>
&#9;def __repr__(self):<br>
&#9;&#9;return str(self)<br>
<br>
&#9;def bulk_norm(self):<br>
&#9;&#9;return (self.x*self.x + self.y*self.y)**0.5<br>
<br>
&#9;def parameter_point(self, t):<br>
&#9;&#9;n = self.bulk_norm()<br>
&#9;&#9;dir_y = self.x / n<br>
&#9;&#9;dir_x = -self.y / n<br>
&#9;&#9;origin = point.origin()<br>
&#9;&#9;c = join.projection_point_line(origin, self).unitized()<br>
&#9;&#9;return point.Point2(<br>
&#9;&#9;&#9;c.x + dir_x * t,<br>
&#9;&#9;&#9;c.y + dir_y * t<br>
&#9;&#9;)<br>
<br>
&#9;def unitized(self):<br>
&#9;&#9;x, y = self.x, self.y<br>
&#9;&#9;n = (x*x + y*y)**0.5<br>
&#9;&#9;return Line2(self.x/n, self.y/n, self.z/n)<br>
<!-- END SCAT CODE -->
</body>
</html>
