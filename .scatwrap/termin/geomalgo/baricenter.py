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
    &quot;&quot;&quot;Compute barycentric coordinates of a point with respect to a simplex.<br>
<br>
    Симплекс выражен как массив вершин. Каждая строка соответствует одной вершине.<br>
    Такой порядок естественнен для описания симплекса как набора точек в пространстве.<br>
<br>
    Args:<br>
        point: A numpy array of shape (n,) representing the point.<br>
        simplex: A numpy array of shape (m, n) representing the vertices of the simplex.<br>
                 For a proper n-simplex, m must equal n+1.<br>
<br>
    Returns:<br>
        A numpy array of shape (m,) representing the barycentric coordinates.<br>
        <br>
    Raises:<br>
        ValueError: If the number of vertices doesn't match the space dimension for a simplex.<br>
<br>
    Notes:<br>
        For a proper simplex in n-dimensional space, you need exactly n+1 vertices.<br>
        Examples:<br>
        - 1D (line segment): 2 vertices<br>
        - 2D (triangle): 3 vertices  <br>
        - 3D (tetrahedron): 4 vertices<br>
    &quot;&quot;&quot;<br>
    m, n = simplex.shape<br>
    <br>
    # Проверка корректности симплекса<br>
    if m != n + 1:<br>
        raise ValueError(<br>
            f&quot;Invalid simplex: expected {n+1} vertices for {n}D space, got {m} vertices. &quot;<br>
            f&quot;A proper n-simplex requires exactly n+1 affinely independent vertices.&quot;<br>
        )<br>
    <br>
    # Строим систему уравнений A @ λ = b<br>
    # A: матрица (n+1) × m, где столбцы - это вершины с добавленной строкой единиц<br>
    # b: точка с добавленной единицей для условия суммы координат<br>
    A = numpy.vstack((simplex.T, numpy.ones((1, m))))<br>
    b = numpy.hstack((point, [1.0]))<br>
    <br>
    # Для квадратной невырожденной матрицы используем numpy.linalg.solve<br>
    # Это быстрее и точнее чем lstsq или inv для хорошо обусловленных систем<br>
    coords = numpy.linalg.solve(A, b)<br>
    return coords<br>
<!-- END SCAT CODE -->
</body>
</html>
