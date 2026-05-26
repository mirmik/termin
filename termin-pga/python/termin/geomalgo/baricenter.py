import numpy


def baricoords_of_point_simplex(point: numpy.ndarray, simplex: numpy.ndarray) -> numpy.ndarray:
    """Compute barycentric coordinates of a point with respect to a simplex.

    Симплекс выражен как массив вершин. Каждая строка соответствует одной вершине.
    Такой порядок естественнен для описания симплекса как набора точек в пространстве.

    Args:
        point: A numpy array of shape (n,) representing the point.
        simplex: A numpy array of shape (m, n) representing the vertices of the simplex.
                 For a proper n-simplex, m must equal n+1.

    Returns:
        A numpy array of shape (m,) representing the barycentric coordinates.
        
    Raises:
        ValueError: If the number of vertices doesn't match the space dimension for a simplex.

    Notes:
        For a proper simplex in n-dimensional space, you need exactly n+1 vertices.
        Examples:
        - 1D (line segment): 2 vertices
        - 2D (triangle): 3 vertices  
        - 3D (tetrahedron): 4 vertices
    """
    m, n = simplex.shape
    
    # Проверка корректности симплекса
    if m != n + 1:
        raise ValueError(
            f"Invalid simplex: expected {n+1} vertices for {n}D space, got {m} vertices. "
            f"A proper n-simplex requires exactly n+1 affinely independent vertices."
        )
    
    # Строим систему уравнений A @ λ = b
    # A: матрица (n+1) × m, где столбцы - это вершины с добавленной строкой единиц
    # b: точка с добавленной единицей для условия суммы координат
    A = numpy.vstack((simplex.T, numpy.ones((1, m))))
    b = numpy.hstack((point, [1.0]))
    
    # Для квадратной невырожденной матрицы используем numpy.linalg.solve
    # Это быстрее и точнее чем lstsq или inv для хорошо обусловленных систем
    coords = numpy.linalg.solve(A, b)
    return coords