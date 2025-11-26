<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ARCHIVE/physics/extlinalg.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import numpy as np<br>
<br>
def outkernel_operator(matrix):<br>
    return matrix @ numpy.linalg.pinv(matrix)<br>
<br>
def kernel_operator(matrix):<br>
    outkernel = outkernel_operator(matrix)<br>
    return numpy.eye(matrix.shape[0]) - outkernel<br>
<!-- END SCAT CODE -->
</body>
</html>
