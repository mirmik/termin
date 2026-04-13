"""Алгебраическая геометрия: квадратичные формы, эллипсоиды, коники."""
import numpy
import math


def fit_quadric(points, center=None):
    """Строит квадратичную форму (квадрику) по набору точек методом наименьших квадратов.
    
    Универсальная функция для восстановления центральных квадрик:
    - Эллипсоид (все собственные значения > 0)
    - Гиперболоид (собственные значения разных знаков)
    
    Квадрика задаётся уравнением: (x-c)ᵀ A (x-c) = ±1, где:
    - A - симметричная матрица (задаёт форму и ориентацию)
    - c - центр квадрики
    
    Args:
        points: Массив точек размера (n_points, n_dim).
                Точки должны приблизительно лежать на поверхности квадрики.
                Минимум n_dim*(n_dim+3)/2 точек для определённости.
        center: Центр квадрики размера (n_dim,).
                Если None, центр определяется автоматически.
                Если задан, строится квадрика с фиксированным центром.
    
    Returns:
        A: Матрица квадратичной формы размера (n_dim, n_dim)
        center: Центр квадрики размера (n_dim,)
    
    Notes:
        Решает задачу наименьших квадратов для общей квадратичной формы:
        x² + B₁₁xy + B₁₂xz + B₂₂y² + B₂₃yz + B₃₃z² + C₁x + C₂y + C₃z + D = 0
        
        Метод не делает предположений о знаках собственных значений A.
        Для специфичных проверок используйте fit_ellipsoid().
    """
    points = numpy.asarray(points, dtype=float)
    
    if points.ndim != 2:
        raise ValueError(f"points должен быть 2D массивом, получен {points.ndim}D")
    
    n_points, n_dim = points.shape
    
    # Минимальное количество точек для определения квадрики
    min_points = n_dim * (n_dim + 3) // 2
    if n_points < min_points:
        raise ValueError(f"Недостаточно точек: нужно минимум {min_points}, получено {n_points}")
    
    # Решаем задачу подгонки
    if center is not None:
        center = numpy.asarray(center, dtype=float)
        if center.shape != (n_dim,):
            raise ValueError(f"center должен иметь размер ({n_dim},), получен {center.shape}")
        A = _fit_quadric_fixed_center(points, center)
    else:
        A, center = _fit_quadric_auto_center(points)
    
    return A, center


def fit_ellipsoid(points, center=None):
    """Строит эллипсоид по набору точек с валидацией и вычислением полуосей.
    
    Эллипсоид задаётся уравнением: (x-c)ᵀ A (x-c) = 1, где:
    - A - положительно определённая матрица (задаёт форму и ориентацию)
    - c - центр эллипсоида
    
    Args:
        points: Массив точек размера (n_points, n_dim).
        center: Центр эллипсоида размера (n_dim,) или None.
    
    Returns:
        A: Матрица квадратичной формы размера (n_dim, n_dim)
        center: Центр эллипсоида размера (n_dim,)
        radii: Полуоси эллипсоида (собственные значения A⁻¹)
        axes: Направления осей (собственные векторы A)
    
    Raises:
        ValueError: Если восстановленная квадрика не является эллипсоидом
    
    Examples:
        >>> # Точки на сфере радиуса 2
        >>> theta = np.linspace(0, 2*np.pi, 50)
        >>> phi = np.linspace(0, np.pi, 50)
        >>> THETA, PHI = np.meshgrid(theta, phi)
        >>> X = 2 * np.sin(PHI) * np.cos(THETA)
        >>> Y = 2 * np.sin(PHI) * np.sin(THETA)
        >>> Z = 2 * np.cos(PHI)
        >>> points = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
        >>> A, center, radii, axes = fit_ellipsoid(points)
        >>> radii  # [2, 2, 2]
    """
    # Восстанавливаем квадрику универсальным методом
    A, center = fit_quadric(points, center)
    
    # Проверяем, что это именно эллипсоид (все собственные значения > 0)
    eigvals, eigvecs = numpy.linalg.eigh(A)
    
    if numpy.any(eigvals <= 0):
        raise ValueError(
            "Получена не положительно определённая матрица. "
            "Точки не лежат на эллипсоиде."
        )
    
    # Вычисляем полуоси = sqrt(1/λᵢ), так как (x-c)ᵀA(x-c) = 1 и A = VΛV^T
    radii = 1.0 / numpy.sqrt(eigvals)
    
    # Сортируем по убыванию полуосей (a ≥ b ≥ c)
    sort_idx = numpy.argsort(radii)[::-1]
    radii = radii[sort_idx]
    axes = eigvecs[:, sort_idx]
    
    return A, center, radii, axes


def fit_hyperboloid(points, center=None):
    """Строит гиперболоид по набору точек с валидацией и анализом типа.
    
    Гиперболоид задаётся уравнением: (x-c)ᵀ A (x-c) = ±1, где:
    - A - матрица со смешанными знаками собственных значений
    - c - центр гиперболоида
    
    Args:
        points: Массив точек размера (n_points, n_dim).
        center: Центр гиперболоида размера (n_dim,) или None.
    
    Returns:
        A: Матрица квадратичной формы размера (n_dim, n_dim)
        center: Центр гиперболоида размера (n_dim,)
        eigvals: Собственные значения (с разными знаками)
        eigvecs: Собственные векторы (главные направления)
        hyperboloid_type: Тип гиперболоида:
            - "one-sheet": однополостный (n-1 положительных, 1 отрицательное)
            - "two-sheet": двуполостный (n-2 положительных, 2 отрицательных)
            - "multi-sheet": многополостный (для размерностей > 3)
    
    Raises:
        ValueError: Если восстановленная квадрика не является гиперболоидом
    
    Examples:
        >>> # Однополостный гиперболоид: x²/4 + y²/4 - z² = 1
        >>> u = np.linspace(0, 2*np.pi, 50)
        >>> v = np.linspace(-2, 2, 50)
        >>> U, V = np.meshgrid(u, v)
        >>> X = 2 * np.cosh(V) * np.cos(U)
        >>> Y = 2 * np.cosh(V) * np.sin(U)
        >>> Z = 2 * np.sinh(V)
        >>> points = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
        >>> A, center, eigvals, eigvecs, htype = fit_hyperboloid(points)
        >>> htype  # "one-sheet"
    """
    # Восстанавливаем квадрику универсальным методом
    A, center = fit_quadric(points, center)
    
    # Анализируем собственные значения
    eigvals, eigvecs = numpy.linalg.eigh(A)
    
    pos_count = numpy.sum(eigvals > 0)
    neg_count = numpy.sum(eigvals < 0)
    n_dim = len(eigvals)
    
    # Проверяем, что это гиперболоид (смешанные знаки)
    if pos_count == n_dim or neg_count == n_dim:
        raise ValueError(
            f"Получена квадрика с собственными значениями одного знака. "
            f"Это эллипсоид, а не гиперболоид. "
            f"Положительных: {pos_count}, отрицательных: {neg_count}"
        )
    
    if pos_count == 0 or neg_count == 0:
        raise ValueError(
            "Получена вырожденная квадрика. "
            "Точки не лежат на гиперболоиде."
        )
    
    # Определяем тип гиперболоида
    if neg_count == 1:
        hyperboloid_type = "one-sheet"
    elif neg_count == 2:
        hyperboloid_type = "two-sheet"
    else:
        hyperboloid_type = "multi-sheet"
    
    return A, center, eigvals, eigvecs, hyperboloid_type


def fit_paraboloid(points):
    """Строит параболоид по набору точек методом линейной регрессии.
    
    Параболоид задаётся уравнением: z = xᵀAx + bᵀx + c, где:
    - A - симметричная матрица размера (n-1, n-1) для координат (x₁,...,xₙ₋₁)
    - b - вектор линейных коэффициентов
    - c - константа
    - z = xₙ - зависимая переменная
    
    Args:
        points: Массив точек размера (n_points, n_dim).
                Последняя координата считается зависимой (высота).
                Минимум n_dim*(n_dim+1)/2 точек.
    
    Returns:
        A: Матрица квадратичной формы размера (n_dim-1, n_dim-1)
        b: Вектор линейных коэффициентов размера (n_dim-1,)
        c: Константа (скаляр)
        vertex: Вершина параболоида размера (n_dim-1,)
        eigvals: Собственные значения матрицы A
        eigvecs: Собственные векторы (главные направления кривизны)
    
    Notes:
        В отличие от эллипсоида/гиперболоида, параболоид не является
        центральной квадрикой. Он решается через линейную регрессию,
        где z явно выражается через остальные координаты.
        
        Для 3D: z = ax² + by² + cxy + dx + ey + f
        
        Вершина находится из условия ∇z = 0: vertex = -½A⁻¹b
    
    Examples:
        >>> # Параболоид вращения: z = x² + y²
        >>> x = np.linspace(-2, 2, 50)
        >>> y = np.linspace(-2, 2, 50)
        >>> X, Y = np.meshgrid(x, y)
        >>> Z = X**2 + Y**2
        >>> points = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
        >>> A, b, c, vertex, eigvals, eigvecs = fit_paraboloid(points)
        >>> vertex  # ≈ [0, 0]
    """
    points = numpy.asarray(points, dtype=float)
    
    if points.ndim != 2:
        raise ValueError(f"points должен быть 2D массивом, получен {points.ndim}D")
    
    n_points, n_dim = points.shape
    
    if n_dim < 2:
        raise ValueError(f"Параболоид требует минимум 2D, получено {n_dim}D")
    
    # Минимальное количество точек для параболоида
    # Для параметров квадратичной формы без z: (n-1)(n-1+1)/2 + (n-1) + 1
    min_points = (n_dim - 1) * (n_dim) // 2 + (n_dim - 1) + 1
    if n_points < min_points:
        raise ValueError(
            f"Недостаточно точек для параболоида: "
            f"нужно минимум {min_points}, получено {n_points}"
        )
    
    # Выделяем независимые координаты (x₁,...,xₙ₋₁) и зависимую (z = xₙ)
    x_coords = points[:, :-1]  # (n_points, n_dim-1)
    z_coords = points[:, -1]   # (n_points,)
    
    n_indep = n_dim - 1
    
    # Строим матрицу дизайна: [x₁², x₁x₂, x₁x₃, x₂², x₂x₃, x₃², x₁, x₂, x₃, 1]
    columns = []
    
    # Квадратичные члены
    for i in range(n_indep):
        for j in range(i, n_indep):
            if i == j:
                columns.append(x_coords[:, i] ** 2)
            else:
                columns.append(x_coords[:, i] * x_coords[:, j])
    
    # Линейные члены
    for i in range(n_indep):
        columns.append(x_coords[:, i])
    
    # Константный член
    columns.append(numpy.ones(n_points))
    
    design_matrix = numpy.column_stack(columns)
    
    # Решаем линейную регрессию: z = design_matrix @ coeffs
    coeffs, residuals, rank, s = numpy.linalg.lstsq(
        design_matrix, z_coords, rcond=None
    )
    
    # Извлекаем коэффициенты
    n_quad = n_indep * (n_indep + 1) // 2
    
    # Восстанавливаем симметричную матрицу A
    A = numpy.zeros((n_indep, n_indep))
    idx = 0
    for i in range(n_indep):
        for j in range(i, n_indep):
            if i == j:
                A[i, j] = coeffs[idx]
            else:
                A[i, j] = coeffs[idx]
                A[j, i] = coeffs[idx]
            idx += 1
    
    # Линейные коэффициенты
    b = coeffs[n_quad:n_quad + n_indep]
    
    # Константа
    c = coeffs[n_quad + n_indep]
    
    # Вычисляем вершину параболоида: точку экстремума
    # ∇z = 2Ax + b = 0 => x = -½A⁻¹b
    try:
        A_inv = numpy.linalg.inv(A)
        vertex = -0.5 * A_inv @ b
    except numpy.linalg.LinAlgError:
        # Вырожденный случай (например, цилиндр)
        vertex = numpy.zeros(n_indep)
        vertex[:] = numpy.nan
    
    # Анализируем кривизну через собственные значения
    eigvals, eigvecs = numpy.linalg.eigh(A)
    
    return A, b, c, vertex, eigvals, eigvecs


def _fit_quadric_fixed_center(points, center):
    """Подгоняет квадрику с заданным центром.
    
    Args:
        points: Массив точек размера (n_points, n_dim)
        center: Центр квадрики размера (n_dim,)
    
    Returns:
        Матрица A размера (n_dim, n_dim)
    """
    n_points, n_dim = points.shape
    
    # Сдвигаем точки к центру
    points_centered = points - center
    
    # Строим матрицу дизайна для квадратичной формы xᵀAx = 1
    design_matrix = _build_quadratic_design_matrix(points_centered)
    
    # Решаем систему: design_matrix @ coeffs = 1
    coeffs, residuals, rank, s = numpy.linalg.lstsq(
        design_matrix, numpy.ones(n_points), rcond=None
    )
    
    # Восстанавливаем симметричную матрицу A из коэффициентов
    A = _coeffs_to_matrix(coeffs, n_dim)
    
    return A


def _fit_quadric_auto_center(points):
    """Подгоняет квадрику с автоматическим определением центра.
    
    Args:
        points: Массив точек размера (n_points, n_dim)
    
    Returns:
        A: Матрица размера (n_dim, n_dim)
        center: Центр размера (n_dim,)
    """
    n_points, n_dim = points.shape
    
    # Строим полную матрицу дизайна: [квадратичные, линейные, константа]
    design_matrix = _build_full_design_matrix(points)
    
    # Решаем однородную систему с ограничением ||coeffs|| = 1
    # Используем SVD: решение = правый сингулярный вектор для минимального σ
    u, s, vh = numpy.linalg.svd(design_matrix, full_matrices=True)
    coeffs = vh[-1, :]
    
    # Извлекаем компоненты
    n_quad = n_dim * (n_dim + 1) // 2
    A = _coeffs_to_matrix(coeffs[:n_quad], n_dim)
    b = coeffs[n_quad:n_quad + n_dim]
    d = coeffs[n_quad + n_dim]
    
    # SVD может дать решение с произвольным знаком
    # Нормализуем так, чтобы след матрицы был положительным
    if numpy.trace(A) < 0:
        A = -A
        b = -b
        d = -d
    
    # Проверяем невырожденность
    eigvals = numpy.linalg.eigvalsh(A)
    if numpy.all(numpy.abs(eigvals) < 1e-10):
        raise ValueError(
            "Получена вырожденная матрица. "
            "Точки не лежат на центральной квадрике."
        )
    
    # Находим центр: c = -½A⁻¹b
    try:
        A_inv = numpy.linalg.inv(A)
        center = -0.5 * A_inv @ b
    except numpy.linalg.LinAlgError:
        raise ValueError(
            "Не удалось найти центр квадрики. "
            "Возможно, точки лежат на параболоиде или вырожденной поверхности."
        )
    
    # Нормализуем к канонической форме (x-c)ᵀA(x-c) = ±1
    k = -(center @ A @ center + b @ center + d)
    
    if numpy.abs(k) < 1e-10:
        raise ValueError("Некорректная нормализация. Проверьте входные данные.")
    
    A = A / k
    
    return A, center


def _build_quadratic_design_matrix(points):
    """Строит матрицу дизайна для квадратичных членов.
    
    Для каждой точки: [x², xy, xz, y², yz, z², ...] (верхний треугольник).
    
    Args:
        points: Массив точек размера (n_points, n_dim)
    
    Returns:
        Матрица дизайна размера (n_points, n_dim*(n_dim+1)/2)
    """
    n_points, n_dim = points.shape
    columns = []
    
    for i in range(n_dim):
        for j in range(i, n_dim):
            if i == j:
                # Диагональные элементы: x², y², z²
                columns.append(points[:, i] ** 2)
            else:
                # Внедиагональные: 2*xy, 2*xz, 2*yz (множитель 2 для симметрии)
                columns.append(2 * points[:, i] * points[:, j])
    
    return numpy.column_stack(columns)


def _build_full_design_matrix(points):
    """Строит полную матрицу дизайна: квадратичные + линейные + константа.
    
    Args:
        points: Массив точек размера (n_points, n_dim)
    
    Returns:
        Матрица дизайна размера (n_points, n_dim*(n_dim+3)/2 + 1)
    """
    n_points, n_dim = points.shape
    
    # Квадратичные члены
    quad_matrix = _build_quadratic_design_matrix(points)
    
    # Линейные члены
    linear_columns = [points[:, i] for i in range(n_dim)]
    
    # Константный член
    const_column = [numpy.ones(n_points)]
    
    return numpy.column_stack([quad_matrix] + linear_columns + const_column)


def _coeffs_to_matrix(coeffs, n_dim):
    """Восстанавливает симметричную матрицу из коэффициентов верхнего треугольника.
    
    Args:
        coeffs: Коэффициенты размера (n_dim*(n_dim+1)/2,)
        n_dim: Размерность матрицы
    
    Returns:
        Симметричная матрица размера (n_dim, n_dim)
    """
    A = numpy.zeros((n_dim, n_dim))
    idx = 0
    
    for i in range(n_dim):
        for j in range(i, n_dim):
            if i == j:
                A[i, j] = coeffs[idx]
            else:
                A[i, j] = coeffs[idx]
                A[j, i] = coeffs[idx]
            idx += 1
    
    return A


def ellipsoid_equation(A, center):
    """Форматирует уравнение эллипсоида в читаемую строку.
    
    Args:
        A: Матрица квадратичной формы размера (n_dim, n_dim)
        center: Центр эллипсоида размера (n_dim,)
    
    Returns:
        Строковое представление уравнения
    """
    n_dim = len(center)
    coord_names = ['x', 'y', 'z', 'w'] + [f'x_{i}' for i in range(4, n_dim)]
    
    terms = []
    for i in range(n_dim):
        ci = center[i]
        coord = coord_names[i]
        if abs(ci) > 1e-10:
            terms.append(f"({coord} - {ci:.3g})")
        else:
            terms.append(coord)
    
    if n_dim <= 3:
        return f"(x-c)ᵀ A (x-c) = 1, где c = {center}"
    else:
        return f"Эллипсоид в R^{n_dim} с центром {center}"


def _gamma_half_integer(n):
    """Вычисляет Γ(n/2 + 1) для натуральных n.
    
    Специализированная функция для вычисления гамма-функции в точках
    вида n/2 + 1, где n — натуральное число. Используется для формулы
    объёма n-мерной сферы/эллипсоида.
    
    Args:
        n: Натуральное число (размерность пространства)
    
    Returns:
        Значение Γ(n/2 + 1)
    
    Notes:
        Для чётных n: Γ(n/2 + 1) = (n/2)!
        Для нечётных n: Γ(n/2 + 1) = Γ(0.5) * ∏(k + 0.5) для k=0..m,
                        где m = (n-1)/2 и Γ(0.5) = √π
        
        Примеры:
        - n=2: Γ(2) = 1! = 1
        - n=3: Γ(2.5) = 1.5 × 0.5 × √π ≈ 1.329
        - n=4: Γ(3) = 2! = 2
    """
    if n % 2 == 0:
        # n чётное: Γ(k+1) = k! для k = n/2
        k = n // 2
        return float(math.factorial(k))
    else:
        # n нечётное: n = 2m + 1, n/2 + 1 = m + 1.5
        # Γ(m + 1.5) = Γ(0.5) * ∏(k + 0.5) для k = 0..m
        # где Γ(0.5) = sqrt(π)
        m = (n - 1) // 2
        gamma_val = numpy.sqrt(numpy.pi)
        for k in range(m + 1):
            gamma_val *= (k + 0.5)
        return gamma_val


def ellipsoid_volume(radii):
    """Вычисляет объём эллипсоида по полуосям.
    
    Args:
        radii: Полуоси эллипсоида размера (n_dim,)
    
    Returns:
        Объём эллипсоида
    
    Notes:
        V = (π^(n/2) / Γ(n/2 + 1)) * ∏rᵢ
        
        Для малых размерностей:
        - 1D: 2r (длина отрезка)
        - 2D: πab (площадь эллипса)
        - 3D: (4/3)πabc (объём эллипсоида)
    """
    radii = numpy.asarray(radii)
    n_dim = len(radii)
    
    # Вычисляем Γ(n/2 + 1) для размерности n
    gamma_val = _gamma_half_integer(n_dim)
    
    # V = (π^(n/2) / Γ(n/2 + 1)) * ∏rᵢ
    half_n = n_dim / 2.0
    volume = (numpy.pi ** half_n / gamma_val) * numpy.prod(radii)
    
    return volume


def evaluate_ellipsoid(points, A, center):
    """Вычисляет значения квадратичной формы эллипсоида в точках.
    
    Для эллипсоида (x-c)ᵀA(x-c) = 1 вычисляет (x-c)ᵀA(x-c) для каждой точки.
    Значения:
    - < 1: точка внутри эллипсоида
    - = 1: точка на поверхности
    - > 1: точка снаружи
    
    Args:
        points: Массив точек размера (n_points, n_dim)
        A: Матрица квадратичной формы размера (n_dim, n_dim)
        center: Центр эллипсоида размера (n_dim,)
    
    Returns:
        Массив значений размера (n_points,)
    """
    points = numpy.asarray(points, dtype=float)
    center = numpy.asarray(center, dtype=float)
    A = numpy.asarray(A, dtype=float)
    
    # Центрируем точки
    points_centered = points - center
    
    # Вычисляем квадратичную форму: (x-c)ᵀA(x-c)
    # Эффективно: sum((A @ p) * p) для каждой точки
    values = numpy.sum((points_centered @ A) * points_centered, axis=1)
    
    return values


def ellipsoid_contains(points, A, center, tol=1e-10):
    """Проверяет, лежат ли точки внутри или на эллипсоиде.
    
    Args:
        points: Массив точек размера (n_points, n_dim)
        A: Матрица квадратичной формы размера (n_dim, n_dim)
        center: Центр эллипсоида размера (n_dim,)
        tol: Допуск для точек на границе
    
    Returns:
        Булев массив размера (n_points,): True если точка внутри/на эллипсоиде
    """
    values = evaluate_ellipsoid(points, A, center)
    return values <= (1.0 + tol)

