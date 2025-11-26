<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ARCHIVE/physics/inertia.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
#!/usr/bin/env python3<br>
<br>
import math<br>
import numpy<br>
<br>
<br>
class Inertia2:<br>
    def __init__(self, mass, inertia):<br>
        self._mass = mass<br>
        self._inertia = inertia<br>
<br>
    def mass(self):<br>
        return self._mass<br>
<br>
    def inertia(self):<br>
        return self._inertia<br>
<br>
    def mass_matrix(self):<br>
        A = self._inertia<br>
        B = numpy.zeros((1, 2))<br>
        C = numpy.zeros((2, 1))<br>
        D = numpy.diag((self.mass, self.mass))<br>
        return numpy.block([<br>
            [A, B],<br>
            [C, D]<br>
        ])<br>
<!-- END SCAT CODE -->
</body>
</html>
