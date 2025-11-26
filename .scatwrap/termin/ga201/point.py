<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ga201/point.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import math<br>
<br>
class Point2:<br>
    def __init__(self, x, y, z=1):<br>
        self.x = x<br>
        self.y = y<br>
        self.z = z<br>
<br>
    def __str__(self):<br>
        return str((self.x, self.y, self.z))<br>
<br>
    def __add__(self, other):<br>
        return Point2(<br>
            self.x + other.x,<br>
            self.y + other.y,<br>
            self.z + other.z<br>
        )<br>
<br>
    def __mul__(self, other):<br>
        return Point2(<br>
            self.x * other,<br>
            self.y * other,<br>
            self.z * other<br>
        )<br>
<br>
    def __sub__(self, other):<br>
        return Point2(<br>
            self.x - other.x,<br>
            self.y - other.y,<br>
            self.z - other.z<br>
        )<br>
<br>
    def __truediv__(self, a):<br>
        return Point2(<br>
            self.x / a,<br>
            self.y / a,<br>
            self.z / a<br>
        )<br>
<br>
    def bulk_norm(self):<br>
        return math.sqrt(self.x*self.x + self.y*self.y)<br>
<br>
    def __str__(self):<br>
        return str((self.x, self.y, self.z))<br>
<br>
    def __repr__(self):<br>
        return str(self)<br>
<br>
    def unitized(self):<br>
        return Point2(<br>
            self.x / self.z,<br>
            self.y / self.z,<br>
            1<br>
        )<br>
<br>
    def is_infinite(self):<br>
        return self.z == 0<br>
<br>
def origin():<br>
    return Point2(0, 0, 1)<br>
<!-- END SCAT CODE -->
</body>
</html>
