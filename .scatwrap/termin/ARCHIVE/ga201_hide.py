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
    grade_dims = [1, 3, 3, 1]<br>
    exterior_dim = sum(grade_dims)<br>
<br>
    def __init__(self, array):<br>
        if len(array) != self.exterior_dim:<br>
            raise Exception(&quot;wrong dimension&quot;)<br>
        self.array = array<br>
<br>
    def __add__(self, other):<br>
        return multivector(self.array + other.array)<br>
<br>
    def __sub__(self, other):<br>
        return multivector(self.array - other.array)<br>
<br>
    def expand(self):<br>
        A = self.array<br>
        return A[0], A[1], A[2], A[3], A[4], A[5], A[6], A[7]<br>
        <br>
    def to_left_prod_operator(self):<br>
        a, a1, a2, a3, a12, a31, a23, a321 = self.expand()<br>
        return numpy.array([<br>
                #e    #e1   #e2       #e3   #e12  #e31   #e23   #e321<br>
             [   a,    a1,    a2,      0,  -a12,     0,     0,     0], <br>
             [  a1,     a,   a12,      0,   -a2,     0,     0,     0], <br>
             [  a2,  -a12,     a,      0,    a1,     0,     0,     0], <br>
             [  a3,   a31,  -a23,      a,  a321,   -a1,    a2,   a12], <br>
             [ a12,   -a2,    a1,      0,     a,     0,     0,     0], <br>
             [ a31,    a3, -a321,    -a1,   a23,     a,  -a12,   -a2], <br>
             [ a23, -a321,   -a3,     a2,  -a31,   a12,     a,   -a1], <br>
             [a321,  -a23,  -a31,   -a12,   -a3,   -a2,   -a1,      a]])<br>
<br>
    def __str__(self):<br>
        return str(self.array)<br>
        <br>
<br>
if __name__ == &quot;__main__&quot;:<br>
    a = multivector(numpy.array([1, 2, 3, 4, 5, 6, 7, 8]))<br>
<br>
    print(a.to_left_prod_operator() @ a.array)<br>
    print(a.expand())<br>
<!-- END SCAT CODE -->
</body>
</html>
