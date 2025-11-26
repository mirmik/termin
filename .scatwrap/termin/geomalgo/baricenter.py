<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/geomalgo/baricenter.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import numpy<br>
<br>
<br>
def baricoords_of_point_simplex(point: numpy.ndarray, simplex: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;&quot;&quot;&quot;Compute barycentric coordinates of a point with respect to a simplex.<br>
<br>
&#9;Симплекс выражен как массив вершин. Каждая строка соответствует одной вершине.<br>
&#9;Такой порядок естественнен для описания симплекса как набора точек в пространстве.<br>
<br>
&#9;Args:<br>
&#9;&#9;point: A numpy array of shape (n,) representing the point.<br>
&#9;&#9;simplex: A numpy array of shape (m, n) representing the vertices of the simplex.<br>
&#9;&#9;&#9;&#9;For a proper n-simplex, m must equal n+1.<br>
<br>
&#9;Returns:<br>
&#9;&#9;A numpy array of shape (m,) representing the barycentric coordinates.<br>
&#9;&#9;<br>
&#9;Raises:<br>
&#9;&#9;ValueError: If the number of vertices doesn't match the space dimension for a simplex.<br>
<br>
&#9;Notes:<br>
&#9;&#9;For a proper simplex in n-dimensional space, you need exactly n+1 vertices.<br>
&#9;&#9;Examples:<br>
&#9;&#9;- 1D (line segment): 2 vertices<br>
&#9;&#9;- 2D (triangle): 3 vertices  <br>
&#9;&#9;- 3D (tetrahedron): 4 vertices<br>
&#9;&quot;&quot;&quot;<br>
&#9;m, n = simplex.shape<br>
&#9;<br>
&#9;# Проверка корректности симплекса<br>
&#9;if m != n + 1:<br>
&#9;&#9;raise ValueError(<br>
&#9;&#9;&#9;f&quot;Invalid simplex: expected {n+1} vertices for {n}D space, got {m} vertices. &quot;<br>
&#9;&#9;&#9;f&quot;A proper n-simplex requires exactly n+1 affinely independent vertices.&quot;<br>
&#9;&#9;)<br>
&#9;<br>
&#9;# Строим систему уравнений A @ λ = b<br>
&#9;# A: матрица (n+1) × m, где столбцы - это вершины с добавленной строкой единиц<br>
&#9;# b: точка с добавленной единицей для условия суммы координат<br>
&#9;A = numpy.vstack((simplex.T, numpy.ones((1, m))))<br>
&#9;b = numpy.hstack((point, [1.0]))<br>
&#9;<br>
&#9;# Для квадратной невырожденной матрицы используем numpy.linalg.solve<br>
&#9;# Это быстрее и точнее чем lstsq или inv для хорошо обусловленных систем<br>
&#9;coords = numpy.linalg.solve(A, b)<br>
&#9;return coords<br>
<!-- END SCAT CODE -->
</body>
</html>
