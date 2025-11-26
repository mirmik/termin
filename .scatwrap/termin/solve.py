<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/solve.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import&nbsp;numpy<br>
<br>
def&nbsp;linear_solve(A,&nbsp;b):<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Решает&nbsp;систему&nbsp;линейных&nbsp;уравнений&nbsp;A&nbsp;@&nbsp;x&nbsp;=&nbsp;b&nbsp;методом&nbsp;наименьших&nbsp;квадратов.<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Использует&nbsp;SVD-разложение&nbsp;(не&nbsp;LU)&nbsp;для&nbsp;численной&nbsp;устойчивости.<br>
&nbsp;&nbsp;&nbsp;&nbsp;Работает&nbsp;для&nbsp;квадратных,&nbsp;переопределённых&nbsp;и&nbsp;недоопределённых&nbsp;систем.<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Args:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A:&nbsp;Матрица&nbsp;коэффициентов&nbsp;размера&nbsp;(m,&nbsp;n)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;b:&nbsp;Вектор&nbsp;правой&nbsp;части&nbsp;размера&nbsp;(m,)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Returns:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Решение&nbsp;x&nbsp;размера&nbsp;(n,)&nbsp;минимизирующее&nbsp;||A@x&nbsp;-&nbsp;b||²<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;im&nbsp;=&nbsp;numpy.linalg.pinv(A)<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;res&nbsp;=&nbsp;im.dot(b)<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;return&nbsp;res<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;numpy.linalg.lstsq(A,&nbsp;b,&nbsp;rcond=None)[0]<br>
<br>
<!-- END SCAT CODE -->
</body>
</html>
