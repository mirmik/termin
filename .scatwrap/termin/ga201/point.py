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
&#9;def __init__(self, x, y, z=1):<br>
&#9;&#9;self.x = x<br>
&#9;&#9;self.y = y<br>
&#9;&#9;self.z = z<br>
<br>
&#9;def __str__(self):<br>
&#9;&#9;return str((self.x, self.y, self.z))<br>
<br>
&#9;def __add__(self, other):<br>
&#9;&#9;return Point2(<br>
&#9;&#9;&#9;self.x + other.x,<br>
&#9;&#9;&#9;self.y + other.y,<br>
&#9;&#9;&#9;self.z + other.z<br>
&#9;&#9;)<br>
<br>
&#9;def __mul__(self, other):<br>
&#9;&#9;return Point2(<br>
&#9;&#9;&#9;self.x * other,<br>
&#9;&#9;&#9;self.y * other,<br>
&#9;&#9;&#9;self.z * other<br>
&#9;&#9;)<br>
<br>
&#9;def __sub__(self, other):<br>
&#9;&#9;return Point2(<br>
&#9;&#9;&#9;self.x - other.x,<br>
&#9;&#9;&#9;self.y - other.y,<br>
&#9;&#9;&#9;self.z - other.z<br>
&#9;&#9;)<br>
<br>
&#9;def __truediv__(self, a):<br>
&#9;&#9;return Point2(<br>
&#9;&#9;&#9;self.x / a,<br>
&#9;&#9;&#9;self.y / a,<br>
&#9;&#9;&#9;self.z / a<br>
&#9;&#9;)<br>
<br>
&#9;def bulk_norm(self):<br>
&#9;&#9;return math.sqrt(self.x*self.x + self.y*self.y)<br>
<br>
&#9;def __str__(self):<br>
&#9;&#9;return str((self.x, self.y, self.z))<br>
<br>
&#9;def __repr__(self):<br>
&#9;&#9;return str(self)<br>
<br>
&#9;def unitized(self):<br>
&#9;&#9;return Point2(<br>
&#9;&#9;&#9;self.x / self.z,<br>
&#9;&#9;&#9;self.y / self.z,<br>
&#9;&#9;&#9;1<br>
&#9;&#9;)<br>
<br>
&#9;def is_infinite(self):<br>
&#9;&#9;return self.z == 0<br>
<br>
def origin():<br>
&#9;return Point2(0, 0, 1)<br>
<!-- END SCAT CODE -->
</body>
</html>
