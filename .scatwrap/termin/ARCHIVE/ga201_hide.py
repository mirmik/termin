<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ARCHIVE/ga201_hide.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env python3<br>
<br>
import numpy<br>
<br>
class multivector:<br>
&#9;grade_dims = [1, 3, 3, 1]<br>
&#9;exterior_dim = sum(grade_dims)<br>
<br>
&#9;def __init__(self, array):<br>
&#9;&#9;if len(array) != self.exterior_dim:<br>
&#9;&#9;&#9;raise Exception(&quot;wrong dimension&quot;)<br>
&#9;&#9;self.array = array<br>
<br>
&#9;def __add__(self, other):<br>
&#9;&#9;return multivector(self.array + other.array)<br>
<br>
&#9;def __sub__(self, other):<br>
&#9;&#9;return multivector(self.array - other.array)<br>
<br>
&#9;def expand(self):<br>
&#9;&#9;A = self.array<br>
&#9;&#9;return A[0], A[1], A[2], A[3], A[4], A[5], A[6], A[7]<br>
&#9;&#9;<br>
&#9;def to_left_prod_operator(self):<br>
&#9;&#9;a, a1, a2, a3, a12, a31, a23, a321 = self.expand()<br>
&#9;&#9;return numpy.array([<br>
&#9;&#9;&#9;&#9;#e    #e1   #e2       #e3   #e12  #e31   #e23   #e321<br>
&#9;&#9;&#9;[   a,    a1,    a2,      0,  -a12,     0,     0,     0], <br>
&#9;&#9;&#9;[  a1,     a,   a12,      0,   -a2,     0,     0,     0], <br>
&#9;&#9;&#9;[  a2,  -a12,     a,      0,    a1,     0,     0,     0], <br>
&#9;&#9;&#9;[  a3,   a31,  -a23,      a,  a321,   -a1,    a2,   a12], <br>
&#9;&#9;&#9;[ a12,   -a2,    a1,      0,     a,     0,     0,     0], <br>
&#9;&#9;&#9;[ a31,    a3, -a321,    -a1,   a23,     a,  -a12,   -a2], <br>
&#9;&#9;&#9;[ a23, -a321,   -a3,     a2,  -a31,   a12,     a,   -a1], <br>
&#9;&#9;&#9;[a321,  -a23,  -a31,   -a12,   -a3,   -a2,   -a1,      a]])<br>
<br>
&#9;def __str__(self):<br>
&#9;&#9;return str(self.array)<br>
&#9;&#9;<br>
<br>
if __name__ == &quot;__main__&quot;:<br>
&#9;a = multivector(numpy.array([1, 2, 3, 4, 5, 6, 7, 8]))<br>
<br>
&#9;print(a.to_left_prod_operator() @ a.array)<br>
&#9;print(a.expand())<br>
<!-- END SCAT CODE -->
</body>
</html>
