<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/algeom.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
&quot;&quot;&quot;Алгебраическая геометрия: квадратичные формы, эллипсоиды, коники.&quot;&quot;&quot;<br>
import numpy<br>
import math<br>
<br>
<br>
def fit_quadric(points, center=None):<br>
    &quot;&quot;&quot;Строит квадратичную форму (квадрику) по набору точек методом наименьших квадратов.<br>
    <br>
    Универсальная функция для восстановления центральных квадрик:<br>
    - Эллипсоид (все собственные значения &gt; 0)<br>
    - Гиперболоид (собственные значения разных знаков)<br>
    <br>
    Квадрика задаётся уравнением: (x-c)ᵀ A (x-c) = ±1, где:<br>
    - A - симметричная матрица (задаёт форму и ориентацию)<br>
    - c - центр квадрики<br>
    <br>
    Args:<br>
        points: Массив точек размера (n_points, n_dim).<br>
                Точки должны приблизительно лежать на поверхности квадрики.<br>
                Минимум n_dim*(n_dim+3)/2 точек для определённости.<br>
        center: Центр квадрики размера (n_dim,).<br>
                Если None, центр определяется автоматически.<br>
                Если задан, строится квадрика с фиксированным центром.<br>
    <br>
    Returns:<br>
        A: Матрица квадратичной формы размера (n_dim, n_dim)<br>
        center: Центр квадрики размера (n_dim,)<br>
    <br>
    Notes:<br>
        Решает задачу наименьших квадратов для общей квадратичной формы:<br>
        x² + B₁₁xy + B₁₂xz + B₂₂y² + B₂₃yz + B₃₃z² + C₁x + C₂y + C₃z + D = 0<br>
        <br>
        Метод не делает предположений о знаках собственных значений A.<br>
        Для специфичных проверок используйте fit_ellipsoid().<br>
    &quot;&quot;&quot;<br>
    points = numpy.asarray(points, dtype=float)<br>
    <br>
    if points.ndim != 2:<br>
        raise ValueError(f&quot;points должен быть 2D массивом, получен {points.ndim}D&quot;)<br>
    <br>
    n_points, n_dim = points.shape<br>
    <br>
    # Минимальное количество точек для определения квадрики<br>
    min_points = n_dim * (n_dim + 3) // 2<br>
    if n_points &lt; min_points:<br>
        raise ValueError(f&quot;Недостаточно точек: нужно минимум {min_points}, получено {n_points}&quot;)<br>
    <br>
    # Решаем задачу подгонки<br>
    if center is not None:<br>
        center = numpy.asarray(center, dtype=float)<br>
        if center.shape != (n_dim,):<br>
            raise ValueError(f&quot;center должен иметь размер ({n_dim},), получен {center.shape}&quot;)<br>
        A = _fit_quadric_fixed_center(points, center)<br>
    else:<br>
        A, center = _fit_quadric_auto_center(points)<br>
    <br>
    return A, center<br>
<br>
<br>
def fit_ellipsoid(points, center=None):<br>
    &quot;&quot;&quot;Строит эллипсоид по набору точек с валидацией и вычислением полуосей.<br>
    <br>
    Эллипсоид задаётся уравнением: (x-c)ᵀ A (x-c) = 1, где:<br>
    - A - положительно определённая матрица (задаёт форму и ориентацию)<br>
    - c - центр эллипсоида<br>
    <br>
    Args:<br>
        points: Массив точек размера (n_points, n_dim).<br>
        center: Центр эллипсоида размера (n_dim,) или None.<br>
    <br>
    Returns:<br>
        A: Матрица квадратичной формы размера (n_dim, n_dim)<br>
        center: Центр эллипсоида размера (n_dim,)<br>
        radii: Полуоси эллипсоида (собственные значения A⁻¹)<br>
        axes: Направления осей (собственные векторы A)<br>
    <br>
    Raises:<br>
        ValueError: Если восстановленная квадрика не является эллипсоидом<br>
    <br>
    Examples:<br>
        &gt;&gt;&gt; # Точки на сфере радиуса 2<br>
        &gt;&gt;&gt; theta = np.linspace(0, 2*np.pi, 50)<br>
        &gt;&gt;&gt; phi = np.linspace(0, np.pi, 50)<br>
        &gt;&gt;&gt; THETA, PHI = np.meshgrid(theta, phi)<br>
        &gt;&gt;&gt; X = 2 * np.sin(PHI) * np.cos(THETA)<br>
        &gt;&gt;&gt; Y = 2 * np.sin(PHI) * np.sin(THETA)<br>
        &gt;&gt;&gt; Z = 2 * np.cos(PHI)<br>
        &gt;&gt;&gt; points = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])<br>
        &gt;&gt;&gt; A, center, radii, axes = fit_ellipsoid(points)<br>
        &gt;&gt;&gt; radii  # [2, 2, 2]<br>
    &quot;&quot;&quot;<br>
    # Восстанавливаем квадрику универсальным методом<br>
    A, center = fit_quadric(points, center)<br>
    <br>
    # Проверяем, что это именно эллипсоид (все собственные значения &gt; 0)<br>
    eigvals, eigvecs = numpy.linalg.eigh(A)<br>
    <br>
    if numpy.any(eigvals &lt;= 0):<br>
        raise ValueError(<br>
            &quot;Получена не положительно определённая матрица. &quot;<br>
            &quot;Точки не лежат на эллипсоиде.&quot;<br>
        )<br>
    <br>
    # Вычисляем полуоси = sqrt(1/λᵢ), так как (x-c)ᵀA(x-c) = 1 и A = VΛV^T<br>
    radii = 1.0 / numpy.sqrt(eigvals)<br>
    <br>
    # Сортируем по убыванию полуосей (a ≥ b ≥ c)<br>
    sort_idx = numpy.argsort(radii)[::-1]<br>
    radii = radii[sort_idx]<br>
    axes = eigvecs[:, sort_idx]<br>
    <br>
    return A, center, radii, axes<br>
<br>
<br>
def fit_hyperboloid(points, center=None):<br>
    &quot;&quot;&quot;Строит гиперболоид по набору точек с валидацией и анализом типа.<br>
    <br>
    Гиперболоид задаётся уравнением: (x-c)ᵀ A (x-c) = ±1, где:<br>
    - A - матрица со смешанными знаками собственных значений<br>
    - c - центр гиперболоида<br>
    <br>
    Args:<br>
        points: Массив точек размера (n_points, n_dim).<br>
        center: Центр гиперболоида размера (n_dim,) или None.<br>
    <br>
    Returns:<br>
        A: Матрица квадратичной формы размера (n_dim, n_dim)<br>
        center: Центр гиперболоида размера (n_dim,)<br>
        eigvals: Собственные значения (с разными знаками)<br>
        eigvecs: Собственные векторы (главные направления)<br>
        hyperboloid_type: Тип гиперболоида:<br>
            - &quot;one-sheet&quot;: однополостный (n-1 положительных, 1 отрицательное)<br>
            - &quot;two-sheet&quot;: двуполостный (n-2 положительных, 2 отрицательных)<br>
            - &quot;multi-sheet&quot;: многополостный (для размерностей &gt; 3)<br>
    <br>
    Raises:<br>
        ValueError: Если восстановленная квадрика не является гиперболоидом<br>
    <br>
    Examples:<br>
        &gt;&gt;&gt; # Однополостный гиперболоид: x²/4 + y²/4 - z² = 1<br>
        &gt;&gt;&gt; u = np.linspace(0, 2*np.pi, 50)<br>
        &gt;&gt;&gt; v = np.linspace(-2, 2, 50)<br>
        &gt;&gt;&gt; U, V = np.meshgrid(u, v)<br>
        &gt;&gt;&gt; X = 2 * np.cosh(V) * np.cos(U)<br>
        &gt;&gt;&gt; Y = 2 * np.cosh(V) * np.sin(U)<br>
        &gt;&gt;&gt; Z = 2 * np.sinh(V)<br>
        &gt;&gt;&gt; points = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])<br>
        &gt;&gt;&gt; A, center, eigvals, eigvecs, htype = fit_hyperboloid(points)<br>
        &gt;&gt;&gt; htype  # &quot;one-sheet&quot;<br>
    &quot;&quot;&quot;<br>
    # Восстанавливаем квадрику универсальным методом<br>
    A, center = fit_quadric(points, center)<br>
    <br>
    # Анализируем собственные значения<br>
    eigvals, eigvecs = numpy.linalg.eigh(A)<br>
    <br>
    pos_count = numpy.sum(eigvals &gt; 0)<br>
    neg_count = numpy.sum(eigvals &lt; 0)<br>
    n_dim = len(eigvals)<br>
    <br>
    # Проверяем, что это гиперболоид (смешанные знаки)<br>
    if pos_count == n_dim or neg_count == n_dim:<br>
        raise ValueError(<br>
            f&quot;Получена квадрика с собственными значениями одного знака. &quot;<br>
            f&quot;Это эллипсоид, а не гиперболоид. &quot;<br>
            f&quot;Положительных: {pos_count}, отрицательных: {neg_count}&quot;<br>
        )<br>
    <br>
    if pos_count == 0 or neg_count == 0:<br>
        raise ValueError(<br>
            &quot;Получена вырожденная квадрика. &quot;<br>
            &quot;Точки не лежат на гиперболоиде.&quot;<br>
        )<br>
    <br>
    # Определяем тип гиперболоида<br>
    if neg_count == 1:<br>
        hyperboloid_type = &quot;one-sheet&quot;<br>
    elif neg_count == 2:<br>
        hyperboloid_type = &quot;two-sheet&quot;<br>
    else:<br>
        hyperboloid_type = &quot;multi-sheet&quot;<br>
    <br>
    return A, center, eigvals, eigvecs, hyperboloid_type<br>
<br>
<br>
def fit_paraboloid(points):<br>
    &quot;&quot;&quot;Строит параболоид по набору точек методом линейной регрессии.<br>
    <br>
    Параболоид задаётся уравнением: z = xᵀAx + bᵀx + c, где:<br>
    - A - симметричная матрица размера (n-1, n-1) для координат (x₁,...,xₙ₋₁)<br>
    - b - вектор линейных коэффициентов<br>
    - c - константа<br>
    - z = xₙ - зависимая переменная<br>
    <br>
    Args:<br>
        points: Массив точек размера (n_points, n_dim).<br>
                Последняя координата считается зависимой (высота).<br>
                Минимум n_dim*(n_dim+1)/2 точек.<br>
    <br>
    Returns:<br>
        A: Матрица квадратичной формы размера (n_dim-1, n_dim-1)<br>
        b: Вектор линейных коэффициентов размера (n_dim-1,)<br>
        c: Константа (скаляр)<br>
        vertex: Вершина параболоида размера (n_dim-1,)<br>
        eigvals: Собственные значения матрицы A<br>
        eigvecs: Собственные векторы (главные направления кривизны)<br>
    <br>
    Notes:<br>
        В отличие от эллипсоида/гиперболоида, параболоид не является<br>
        центральной квадрикой. Он решается через линейную регрессию,<br>
        где z явно выражается через остальные координаты.<br>
        <br>
        Для 3D: z = ax² + by² + cxy + dx + ey + f<br>
        <br>
        Вершина находится из условия ∇z = 0: vertex = -½A⁻¹b<br>
    <br>
    Examples:<br>
        &gt;&gt;&gt; # Параболоид вращения: z = x² + y²<br>
        &gt;&gt;&gt; x = np.linspace(-2, 2, 50)<br>
        &gt;&gt;&gt; y = np.linspace(-2, 2, 50)<br>
        &gt;&gt;&gt; X, Y = np.meshgrid(x, y)<br>
        &gt;&gt;&gt; Z = X**2 + Y**2<br>
        &gt;&gt;&gt; points = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])<br>
        &gt;&gt;&gt; A, b, c, vertex, eigvals, eigvecs = fit_paraboloid(points)<br>
        &gt;&gt;&gt; vertex  # ≈ [0, 0]<br>
    &quot;&quot;&quot;<br>
    points = numpy.asarray(points, dtype=float)<br>
    <br>
    if points.ndim != 2:<br>
        raise ValueError(f&quot;points должен быть 2D массивом, получен {points.ndim}D&quot;)<br>
    <br>
    n_points, n_dim = points.shape<br>
    <br>
    if n_dim &lt; 2:<br>
        raise ValueError(f&quot;Параболоид требует минимум 2D, получено {n_dim}D&quot;)<br>
    <br>
    # Минимальное количество точек для параболоида<br>
    # Для параметров квадратичной формы без z: (n-1)(n-1+1)/2 + (n-1) + 1<br>
    min_points = (n_dim - 1) * (n_dim) // 2 + (n_dim - 1) + 1<br>
    if n_points &lt; min_points:<br>
        raise ValueError(<br>
            f&quot;Недостаточно точек для параболоида: &quot;<br>
            f&quot;нужно минимум {min_points}, получено {n_points}&quot;<br>
        )<br>
    <br>
    # Выделяем независимые координаты (x₁,...,xₙ₋₁) и зависимую (z = xₙ)<br>
    x_coords = points[:, :-1]  # (n_points, n_dim-1)<br>
    z_coords = points[:, -1]   # (n_points,)<br>
    <br>
    n_indep = n_dim - 1<br>
    <br>
    # Строим матрицу дизайна: [x₁², x₁x₂, x₁x₃, x₂², x₂x₃, x₃², x₁, x₂, x₃, 1]<br>
    columns = []<br>
    <br>
    # Квадратичные члены<br>
    for i in range(n_indep):<br>
        for j in range(i, n_indep):<br>
            if i == j:<br>
                columns.append(x_coords[:, i] ** 2)<br>
            else:<br>
                columns.append(x_coords[:, i] * x_coords[:, j])<br>
    <br>
    # Линейные члены<br>
    for i in range(n_indep):<br>
        columns.append(x_coords[:, i])<br>
    <br>
    # Константный член<br>
    columns.append(numpy.ones(n_points))<br>
    <br>
    design_matrix = numpy.column_stack(columns)<br>
    <br>
    # Решаем линейную регрессию: z = design_matrix @ coeffs<br>
    coeffs, residuals, rank, s = numpy.linalg.lstsq(<br>
        design_matrix, z_coords, rcond=None<br>
    )<br>
    <br>
    # Извлекаем коэффициенты<br>
    n_quad = n_indep * (n_indep + 1) // 2<br>
    <br>
    # Восстанавливаем симметричную матрицу A<br>
    A = numpy.zeros((n_indep, n_indep))<br>
    idx = 0<br>
    for i in range(n_indep):<br>
        for j in range(i, n_indep):<br>
            if i == j:<br>
                A[i, j] = coeffs[idx]<br>
            else:<br>
                A[i, j] = coeffs[idx]<br>
                A[j, i] = coeffs[idx]<br>
            idx += 1<br>
    <br>
    # Линейные коэффициенты<br>
    b = coeffs[n_quad:n_quad + n_indep]<br>
    <br>
    # Константа<br>
    c = coeffs[n_quad + n_indep]<br>
    <br>
    # Вычисляем вершину параболоида: точку экстремума<br>
    # ∇z = 2Ax + b = 0 =&gt; x = -½A⁻¹b<br>
    try:<br>
        A_inv = numpy.linalg.inv(A)<br>
        vertex = -0.5 * A_inv @ b<br>
    except numpy.linalg.LinAlgError:<br>
        # Вырожденный случай (например, цилиндр)<br>
        vertex = numpy.zeros(n_indep)<br>
        vertex[:] = numpy.nan<br>
    <br>
    # Анализируем кривизну через собственные значения<br>
    eigvals, eigvecs = numpy.linalg.eigh(A)<br>
    <br>
    return A, b, c, vertex, eigvals, eigvecs<br>
<br>
<br>
def _fit_quadric_fixed_center(points, center):<br>
    &quot;&quot;&quot;Подгоняет квадрику с заданным центром.<br>
    <br>
    Args:<br>
        points: Массив точек размера (n_points, n_dim)<br>
        center: Центр квадрики размера (n_dim,)<br>
    <br>
    Returns:<br>
        Матрица A размера (n_dim, n_dim)<br>
    &quot;&quot;&quot;<br>
    n_points, n_dim = points.shape<br>
    <br>
    # Сдвигаем точки к центру<br>
    points_centered = points - center<br>
    <br>
    # Строим матрицу дизайна для квадратичной формы xᵀAx = 1<br>
    design_matrix = _build_quadratic_design_matrix(points_centered)<br>
    <br>
    # Решаем систему: design_matrix @ coeffs = 1<br>
    coeffs, residuals, rank, s = numpy.linalg.lstsq(<br>
        design_matrix, numpy.ones(n_points), rcond=None<br>
    )<br>
    <br>
    # Восстанавливаем симметричную матрицу A из коэффициентов<br>
    A = _coeffs_to_matrix(coeffs, n_dim)<br>
    <br>
    return A<br>
<br>
<br>
def _fit_quadric_auto_center(points):<br>
    &quot;&quot;&quot;Подгоняет квадрику с автоматическим определением центра.<br>
    <br>
    Args:<br>
        points: Массив точек размера (n_points, n_dim)<br>
    <br>
    Returns:<br>
        A: Матрица размера (n_dim, n_dim)<br>
        center: Центр размера (n_dim,)<br>
    &quot;&quot;&quot;<br>
    n_points, n_dim = points.shape<br>
    <br>
    # Строим полную матрицу дизайна: [квадратичные, линейные, константа]<br>
    design_matrix = _build_full_design_matrix(points)<br>
    <br>
    # Решаем однородную систему с ограничением ||coeffs|| = 1<br>
    # Используем SVD: решение = правый сингулярный вектор для минимального σ<br>
    u, s, vh = numpy.linalg.svd(design_matrix, full_matrices=True)<br>
    coeffs = vh[-1, :]<br>
    <br>
    # Извлекаем компоненты<br>
    n_quad = n_dim * (n_dim + 1) // 2<br>
    A = _coeffs_to_matrix(coeffs[:n_quad], n_dim)<br>
    b = coeffs[n_quad:n_quad + n_dim]<br>
    d = coeffs[n_quad + n_dim]<br>
    <br>
    # SVD может дать решение с произвольным знаком<br>
    # Нормализуем так, чтобы след матрицы был положительным<br>
    if numpy.trace(A) &lt; 0:<br>
        A = -A<br>
        b = -b<br>
        d = -d<br>
    <br>
    # Проверяем невырожденность<br>
    eigvals = numpy.linalg.eigvalsh(A)<br>
    if numpy.all(numpy.abs(eigvals) &lt; 1e-10):<br>
        raise ValueError(<br>
            &quot;Получена вырожденная матрица. &quot;<br>
            &quot;Точки не лежат на центральной квадрике.&quot;<br>
        )<br>
    <br>
    # Находим центр: c = -½A⁻¹b<br>
    try:<br>
        A_inv = numpy.linalg.inv(A)<br>
        center = -0.5 * A_inv @ b<br>
    except numpy.linalg.LinAlgError:<br>
        raise ValueError(<br>
            &quot;Не удалось найти центр квадрики. &quot;<br>
            &quot;Возможно, точки лежат на параболоиде или вырожденной поверхности.&quot;<br>
        )<br>
    <br>
    # Нормализуем к канонической форме (x-c)ᵀA(x-c) = ±1<br>
    k = -(center @ A @ center + b @ center + d)<br>
    <br>
    if numpy.abs(k) &lt; 1e-10:<br>
        raise ValueError(&quot;Некорректная нормализация. Проверьте входные данные.&quot;)<br>
    <br>
    A = A / k<br>
    <br>
    return A, center<br>
<br>
<br>
def _build_quadratic_design_matrix(points):<br>
    &quot;&quot;&quot;Строит матрицу дизайна для квадратичных членов.<br>
    <br>
    Для каждой точки: [x², xy, xz, y², yz, z², ...] (верхний треугольник).<br>
    <br>
    Args:<br>
        points: Массив точек размера (n_points, n_dim)<br>
    <br>
    Returns:<br>
        Матрица дизайна размера (n_points, n_dim*(n_dim+1)/2)<br>
    &quot;&quot;&quot;<br>
    n_points, n_dim = points.shape<br>
    columns = []<br>
    <br>
    for i in range(n_dim):<br>
        for j in range(i, n_dim):<br>
            if i == j:<br>
                # Диагональные элементы: x², y², z²<br>
                columns.append(points[:, i] ** 2)<br>
            else:<br>
                # Внедиагональные: 2*xy, 2*xz, 2*yz (множитель 2 для симметрии)<br>
                columns.append(2 * points[:, i] * points[:, j])<br>
    <br>
    return numpy.column_stack(columns)<br>
<br>
<br>
def _build_full_design_matrix(points):<br>
    &quot;&quot;&quot;Строит полную матрицу дизайна: квадратичные + линейные + константа.<br>
    <br>
    Args:<br>
        points: Массив точек размера (n_points, n_dim)<br>
    <br>
    Returns:<br>
        Матрица дизайна размера (n_points, n_dim*(n_dim+3)/2 + 1)<br>
    &quot;&quot;&quot;<br>
    n_points, n_dim = points.shape<br>
    <br>
    # Квадратичные члены<br>
    quad_matrix = _build_quadratic_design_matrix(points)<br>
    <br>
    # Линейные члены<br>
    linear_columns = [points[:, i] for i in range(n_dim)]<br>
    <br>
    # Константный член<br>
    const_column = [numpy.ones(n_points)]<br>
    <br>
    return numpy.column_stack([quad_matrix] + linear_columns + const_column)<br>
<br>
<br>
def _coeffs_to_matrix(coeffs, n_dim):<br>
    &quot;&quot;&quot;Восстанавливает симметричную матрицу из коэффициентов верхнего треугольника.<br>
    <br>
    Args:<br>
        coeffs: Коэффициенты размера (n_dim*(n_dim+1)/2,)<br>
        n_dim: Размерность матрицы<br>
    <br>
    Returns:<br>
        Симметричная матрица размера (n_dim, n_dim)<br>
    &quot;&quot;&quot;<br>
    A = numpy.zeros((n_dim, n_dim))<br>
    idx = 0<br>
    <br>
    for i in range(n_dim):<br>
        for j in range(i, n_dim):<br>
            if i == j:<br>
                A[i, j] = coeffs[idx]<br>
            else:<br>
                A[i, j] = coeffs[idx]<br>
                A[j, i] = coeffs[idx]<br>
            idx += 1<br>
    <br>
    return A<br>
<br>
<br>
def ellipsoid_equation(A, center):<br>
    &quot;&quot;&quot;Форматирует уравнение эллипсоида в читаемую строку.<br>
    <br>
    Args:<br>
        A: Матрица квадратичной формы размера (n_dim, n_dim)<br>
        center: Центр эллипсоида размера (n_dim,)<br>
    <br>
    Returns:<br>
        Строковое представление уравнения<br>
    &quot;&quot;&quot;<br>
    n_dim = len(center)<br>
    coord_names = ['x', 'y', 'z', 'w'] + [f'x_{i}' for i in range(4, n_dim)]<br>
    <br>
    terms = []<br>
    for i in range(n_dim):<br>
        ci = center[i]<br>
        coord = coord_names[i]<br>
        if abs(ci) &gt; 1e-10:<br>
            terms.append(f&quot;({coord} - {ci:.3g})&quot;)<br>
        else:<br>
            terms.append(coord)<br>
    <br>
    if n_dim &lt;= 3:<br>
        return f&quot;(x-c)ᵀ A (x-c) = 1, где c = {center}&quot;<br>
    else:<br>
        return f&quot;Эллипсоид в R^{n_dim} с центром {center}&quot;<br>
<br>
<br>
def _gamma_half_integer(n):<br>
    &quot;&quot;&quot;Вычисляет Γ(n/2 + 1) для натуральных n.<br>
    <br>
    Специализированная функция для вычисления гамма-функции в точках<br>
    вида n/2 + 1, где n — натуральное число. Используется для формулы<br>
    объёма n-мерной сферы/эллипсоида.<br>
    <br>
    Args:<br>
        n: Натуральное число (размерность пространства)<br>
    <br>
    Returns:<br>
        Значение Γ(n/2 + 1)<br>
    <br>
    Notes:<br>
        Для чётных n: Γ(n/2 + 1) = (n/2)!<br>
        Для нечётных n: Γ(n/2 + 1) = Γ(0.5) * ∏(k + 0.5) для k=0..m,<br>
                        где m = (n-1)/2 и Γ(0.5) = √π<br>
        <br>
        Примеры:<br>
        - n=2: Γ(2) = 1! = 1<br>
        - n=3: Γ(2.5) = 1.5 × 0.5 × √π ≈ 1.329<br>
        - n=4: Γ(3) = 2! = 2<br>
    &quot;&quot;&quot;<br>
    if n % 2 == 0:<br>
        # n чётное: Γ(k+1) = k! для k = n/2<br>
        k = n // 2<br>
        return float(math.factorial(k))<br>
    else:<br>
        # n нечётное: n = 2m + 1, n/2 + 1 = m + 1.5<br>
        # Γ(m + 1.5) = Γ(0.5) * ∏(k + 0.5) для k = 0..m<br>
        # где Γ(0.5) = sqrt(π)<br>
        m = (n - 1) // 2<br>
        gamma_val = numpy.sqrt(numpy.pi)<br>
        for k in range(m + 1):<br>
            gamma_val *= (k + 0.5)<br>
        return gamma_val<br>
<br>
<br>
def ellipsoid_volume(radii):<br>
    &quot;&quot;&quot;Вычисляет объём эллипсоида по полуосям.<br>
    <br>
    Args:<br>
        radii: Полуоси эллипсоида размера (n_dim,)<br>
    <br>
    Returns:<br>
        Объём эллипсоида<br>
    <br>
    Notes:<br>
        V = (π^(n/2) / Γ(n/2 + 1)) * ∏rᵢ<br>
        <br>
        Для малых размерностей:<br>
        - 1D: 2r (длина отрезка)<br>
        - 2D: πab (площадь эллипса)<br>
        - 3D: (4/3)πabc (объём эллипсоида)<br>
    &quot;&quot;&quot;<br>
    radii = numpy.asarray(radii)<br>
    n_dim = len(radii)<br>
    <br>
    # Вычисляем Γ(n/2 + 1) для размерности n<br>
    gamma_val = _gamma_half_integer(n_dim)<br>
    <br>
    # V = (π^(n/2) / Γ(n/2 + 1)) * ∏rᵢ<br>
    half_n = n_dim / 2.0<br>
    volume = (numpy.pi ** half_n / gamma_val) * numpy.prod(radii)<br>
    <br>
    return volume<br>
<br>
<br>
def evaluate_ellipsoid(points, A, center):<br>
    &quot;&quot;&quot;Вычисляет значения квадратичной формы эллипсоида в точках.<br>
    <br>
    Для эллипсоида (x-c)ᵀA(x-c) = 1 вычисляет (x-c)ᵀA(x-c) для каждой точки.<br>
    Значения:<br>
    - &lt; 1: точка внутри эллипсоида<br>
    - = 1: точка на поверхности<br>
    - &gt; 1: точка снаружи<br>
    <br>
    Args:<br>
        points: Массив точек размера (n_points, n_dim)<br>
        A: Матрица квадратичной формы размера (n_dim, n_dim)<br>
        center: Центр эллипсоида размера (n_dim,)<br>
    <br>
    Returns:<br>
        Массив значений размера (n_points,)<br>
    &quot;&quot;&quot;<br>
    points = numpy.asarray(points, dtype=float)<br>
    center = numpy.asarray(center, dtype=float)<br>
    A = numpy.asarray(A, dtype=float)<br>
    <br>
    # Центрируем точки<br>
    points_centered = points - center<br>
    <br>
    # Вычисляем квадратичную форму: (x-c)ᵀA(x-c)<br>
    # Эффективно: sum((A @ p) * p) для каждой точки<br>
    values = numpy.sum((points_centered @ A) * points_centered, axis=1)<br>
    <br>
    return values<br>
<br>
<br>
def ellipsoid_contains(points, A, center, tol=1e-10):<br>
    &quot;&quot;&quot;Проверяет, лежат ли точки внутри или на эллипсоиде.<br>
    <br>
    Args:<br>
        points: Массив точек размера (n_points, n_dim)<br>
        A: Матрица квадратичной формы размера (n_dim, n_dim)<br>
        center: Центр эллипсоида размера (n_dim,)<br>
        tol: Допуск для точек на границе<br>
    <br>
    Returns:<br>
        Булев массив размера (n_points,): True если точка внутри/на эллипсоиде<br>
    &quot;&quot;&quot;<br>
    values = evaluate_ellipsoid(points, A, center)<br>
    return values &lt;= (1.0 + tol)<br>
<br>
<!-- END SCAT CODE -->
</body>
</html>
