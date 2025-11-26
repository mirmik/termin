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
    &quot;&quot;&quot;Решает систему линейных уравнений A @ x = b методом наименьших квадратов.<br>
    <br>
    Использует SVD-разложение (не LU) для численной устойчивости.<br>
    Работает для квадратных, переопределённых и недоопределённых систем.<br>
    <br>
    Args:<br>
        A: Матрица коэффициентов размера (m, n)<br>
        b: Вектор правой части размера (m,)<br>
        <br>
    Returns:<br>
        Решение x размера (n,) минимизирующее ||A@x - b||²<br>
    &quot;&quot;&quot;<br>
    # im = numpy.linalg.pinv(A)<br>
    # res = im.dot(b)<br>
    # return res<br>
    return numpy.linalg.lstsq(A, b, rcond=None)[0]<br>
<br>
<!-- END SCAT CODE -->
</body>
</html>
