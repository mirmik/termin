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
&#9;def __init__(self, mass, inertia):<br>
&#9;&#9;self._mass = mass<br>
&#9;&#9;self._inertia = inertia<br>
<br>
&#9;def mass(self):<br>
&#9;&#9;return self._mass<br>
<br>
&#9;def inertia(self):<br>
&#9;&#9;return self._inertia<br>
<br>
&#9;def mass_matrix(self):<br>
&#9;&#9;A = self._inertia<br>
&#9;&#9;B = numpy.zeros((1, 2))<br>
&#9;&#9;C = numpy.zeros((2, 1))<br>
&#9;&#9;D = numpy.diag((self.mass, self.mass))<br>
&#9;&#9;return numpy.block([<br>
&#9;&#9;&#9;[A, B],<br>
&#9;&#9;&#9;[C, D]<br>
&#9;&#9;])<br>
<!-- END SCAT CODE -->
</body>
</html>
