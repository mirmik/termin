<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/ARCHIVE/physics/extlinalg.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import&nbsp;numpy&nbsp;as&nbsp;np<br>
<br>
def&nbsp;outkernel_operator(matrix):<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;matrix&nbsp;@&nbsp;numpy.linalg.pinv(matrix)<br>
<br>
def&nbsp;kernel_operator(matrix):<br>
&nbsp;&nbsp;&nbsp;&nbsp;outkernel&nbsp;=&nbsp;outkernel_operator(matrix)<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;numpy.eye(matrix.shape[0])&nbsp;-&nbsp;outkernel<br>
<!-- END SCAT CODE -->
</body>
</html>
