<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/solve.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import numpy<br>
<br>
def linear_solve(A, b):<br>
&#9;&quot;&quot;&quot;Решает систему линейных уравнений A @ x = b методом наименьших квадратов.<br>
&#9;<br>
&#9;Использует SVD-разложение (не LU) для численной устойчивости.<br>
&#9;Работает для квадратных, переопределённых и недоопределённых систем.<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;A: Матрица коэффициентов размера (m, n)<br>
&#9;&#9;b: Вектор правой части размера (m,)<br>
&#9;&#9;<br>
&#9;Returns:<br>
&#9;&#9;Решение x размера (n,) минимизирующее ||A@x - b||²<br>
&#9;&quot;&quot;&quot;<br>
&#9;# im = numpy.linalg.pinv(A)<br>
&#9;# res = im.dot(b)<br>
&#9;# return res<br>
&#9;return numpy.linalg.lstsq(A, b, rcond=None)[0]<br>
<br>
<!-- END SCAT CODE -->
</body>
</html>
