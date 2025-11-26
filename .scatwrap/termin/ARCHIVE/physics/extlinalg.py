<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ARCHIVE/physics/extlinalg.py</title>
</head>
<body>
<pre><code>
import numpy as np

def outkernel_operator(matrix):
    return matrix @ numpy.linalg.pinv(matrix)

def kernel_operator(matrix):
    outkernel = outkernel_operator(matrix)
    return numpy.eye(matrix.shape[0]) - outkernel

</code></pre>
</body>
</html>
