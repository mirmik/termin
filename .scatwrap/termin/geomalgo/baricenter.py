<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/geomalgo/baricenter.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import&nbsp;numpy<br>
<br>
<br>
def&nbsp;baricoords_of_point_simplex(point:&nbsp;numpy.ndarray,&nbsp;simplex:&nbsp;numpy.ndarray)&nbsp;-&gt;&nbsp;numpy.ndarray:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;Compute&nbsp;barycentric&nbsp;coordinates&nbsp;of&nbsp;a&nbsp;point&nbsp;with&nbsp;respect&nbsp;to&nbsp;a&nbsp;simplex.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;Симплекс&nbsp;выражен&nbsp;как&nbsp;массив&nbsp;вершин.&nbsp;Каждая&nbsp;строка&nbsp;соответствует&nbsp;одной&nbsp;вершине.<br>
&nbsp;&nbsp;&nbsp;&nbsp;Такой&nbsp;порядок&nbsp;естественнен&nbsp;для&nbsp;описания&nbsp;симплекса&nbsp;как&nbsp;набора&nbsp;точек&nbsp;в&nbsp;пространстве.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;Args:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;point:&nbsp;A&nbsp;numpy&nbsp;array&nbsp;of&nbsp;shape&nbsp;(n,)&nbsp;representing&nbsp;the&nbsp;point.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;simplex:&nbsp;A&nbsp;numpy&nbsp;array&nbsp;of&nbsp;shape&nbsp;(m,&nbsp;n)&nbsp;representing&nbsp;the&nbsp;vertices&nbsp;of&nbsp;the&nbsp;simplex.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;For&nbsp;a&nbsp;proper&nbsp;n-simplex,&nbsp;m&nbsp;must&nbsp;equal&nbsp;n+1.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;Returns:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;A&nbsp;numpy&nbsp;array&nbsp;of&nbsp;shape&nbsp;(m,)&nbsp;representing&nbsp;the&nbsp;barycentric&nbsp;coordinates.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;Raises:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ValueError:&nbsp;If&nbsp;the&nbsp;number&nbsp;of&nbsp;vertices&nbsp;doesn't&nbsp;match&nbsp;the&nbsp;space&nbsp;dimension&nbsp;for&nbsp;a&nbsp;simplex.<br>
<br>
&nbsp;&nbsp;&nbsp;&nbsp;Notes:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;For&nbsp;a&nbsp;proper&nbsp;simplex&nbsp;in&nbsp;n-dimensional&nbsp;space,&nbsp;you&nbsp;need&nbsp;exactly&nbsp;n+1&nbsp;vertices.<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Examples:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;1D&nbsp;(line&nbsp;segment):&nbsp;2&nbsp;vertices<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;2D&nbsp;(triangle):&nbsp;3&nbsp;vertices&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;3D&nbsp;(tetrahedron):&nbsp;4&nbsp;vertices<br>
&nbsp;&nbsp;&nbsp;&nbsp;&quot;&quot;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;m,&nbsp;n&nbsp;=&nbsp;simplex.shape<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Проверка&nbsp;корректности&nbsp;симплекса<br>
&nbsp;&nbsp;&nbsp;&nbsp;if&nbsp;m&nbsp;!=&nbsp;n&nbsp;+&nbsp;1:<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;raise&nbsp;ValueError(<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;f&quot;Invalid&nbsp;simplex:&nbsp;expected&nbsp;{n+1}&nbsp;vertices&nbsp;for&nbsp;{n}D&nbsp;space,&nbsp;got&nbsp;{m}&nbsp;vertices.&nbsp;&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;f&quot;A&nbsp;proper&nbsp;n-simplex&nbsp;requires&nbsp;exactly&nbsp;n+1&nbsp;affinely&nbsp;independent&nbsp;vertices.&quot;<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;)<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Строим&nbsp;систему&nbsp;уравнений&nbsp;A&nbsp;@&nbsp;λ&nbsp;=&nbsp;b<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;A:&nbsp;матрица&nbsp;(n+1)&nbsp;×&nbsp;m,&nbsp;где&nbsp;столбцы&nbsp;-&nbsp;это&nbsp;вершины&nbsp;с&nbsp;добавленной&nbsp;строкой&nbsp;единиц<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;b:&nbsp;точка&nbsp;с&nbsp;добавленной&nbsp;единицей&nbsp;для&nbsp;условия&nbsp;суммы&nbsp;координат<br>
&nbsp;&nbsp;&nbsp;&nbsp;A&nbsp;=&nbsp;numpy.vstack((simplex.T,&nbsp;numpy.ones((1,&nbsp;m))))<br>
&nbsp;&nbsp;&nbsp;&nbsp;b&nbsp;=&nbsp;numpy.hstack((point,&nbsp;[1.0]))<br>
&nbsp;&nbsp;&nbsp;&nbsp;<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Для&nbsp;квадратной&nbsp;невырожденной&nbsp;матрицы&nbsp;используем&nbsp;numpy.linalg.solve<br>
&nbsp;&nbsp;&nbsp;&nbsp;#&nbsp;Это&nbsp;быстрее&nbsp;и&nbsp;точнее&nbsp;чем&nbsp;lstsq&nbsp;или&nbsp;inv&nbsp;для&nbsp;хорошо&nbsp;обусловленных&nbsp;систем<br>
&nbsp;&nbsp;&nbsp;&nbsp;coords&nbsp;=&nbsp;numpy.linalg.solve(A,&nbsp;b)<br>
&nbsp;&nbsp;&nbsp;&nbsp;return&nbsp;coords<br>
<!-- END SCAT CODE -->
</body>
</html>
