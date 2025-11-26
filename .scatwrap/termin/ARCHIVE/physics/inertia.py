<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ARCHIVE/physics/inertia.py</title>
</head>
<body>
<pre><code>
#!/usr/bin/env python3

import math
import numpy


class Inertia2:
    def __init__(self, mass, inertia):
        self._mass = mass
        self._inertia = inertia

    def mass(self):
        return self._mass

    def inertia(self):
        return self._inertia

    def mass_matrix(self):
        A = self._inertia
        B = numpy.zeros((1, 2))
        C = numpy.zeros((2, 1))
        D = numpy.diag((self.mass, self.mass))
        return numpy.block([
            [A, B],
            [C, D]
        ])

</code></pre>
</body>
</html>
