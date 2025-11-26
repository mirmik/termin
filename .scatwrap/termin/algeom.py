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
&#9;&quot;&quot;&quot;Строит квадратичную форму (квадрику) по набору точек методом наименьших квадратов.<br>
&#9;<br>
&#9;Универсальная функция для восстановления центральных квадрик:<br>
&#9;- Эллипсоид (все собственные значения &gt; 0)<br>
&#9;- Гиперболоид (собственные значения разных знаков)<br>
&#9;<br>
&#9;Квадрика задаётся уравнением: (x-c)ᵀ A (x-c) = ±1, где:<br>
&#9;- A - симметричная матрица (задаёт форму и ориентацию)<br>
&#9;- c - центр квадрики<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;points: Массив точек размера (n_points, n_dim).<br>
&#9;&#9;&#9;&#9;Точки должны приблизительно лежать на поверхности квадрики.<br>
&#9;&#9;&#9;&#9;Минимум n_dim*(n_dim+3)/2 точек для определённости.<br>
&#9;&#9;center: Центр квадрики размера (n_dim,).<br>
&#9;&#9;&#9;&#9;Если None, центр определяется автоматически.<br>
&#9;&#9;&#9;&#9;Если задан, строится квадрика с фиксированным центром.<br>
&#9;<br>
&#9;Returns:<br>
&#9;&#9;A: Матрица квадратичной формы размера (n_dim, n_dim)<br>
&#9;&#9;center: Центр квадрики размера (n_dim,)<br>
&#9;<br>
&#9;Notes:<br>
&#9;&#9;Решает задачу наименьших квадратов для общей квадратичной формы:<br>
&#9;&#9;x² + B₁₁xy + B₁₂xz + B₂₂y² + B₂₃yz + B₃₃z² + C₁x + C₂y + C₃z + D = 0<br>
&#9;&#9;<br>
&#9;&#9;Метод не делает предположений о знаках собственных значений A.<br>
&#9;&#9;Для специфичных проверок используйте fit_ellipsoid().<br>
&#9;&quot;&quot;&quot;<br>
&#9;points = numpy.asarray(points, dtype=float)<br>
&#9;<br>
&#9;if points.ndim != 2:<br>
&#9;&#9;raise ValueError(f&quot;points должен быть 2D массивом, получен {points.ndim}D&quot;)<br>
&#9;<br>
&#9;n_points, n_dim = points.shape<br>
&#9;<br>
&#9;# Минимальное количество точек для определения квадрики<br>
&#9;min_points = n_dim * (n_dim + 3) // 2<br>
&#9;if n_points &lt; min_points:<br>
&#9;&#9;raise ValueError(f&quot;Недостаточно точек: нужно минимум {min_points}, получено {n_points}&quot;)<br>
&#9;<br>
&#9;# Решаем задачу подгонки<br>
&#9;if center is not None:<br>
&#9;&#9;center = numpy.asarray(center, dtype=float)<br>
&#9;&#9;if center.shape != (n_dim,):<br>
&#9;&#9;&#9;raise ValueError(f&quot;center должен иметь размер ({n_dim},), получен {center.shape}&quot;)<br>
&#9;&#9;A = _fit_quadric_fixed_center(points, center)<br>
&#9;else:<br>
&#9;&#9;A, center = _fit_quadric_auto_center(points)<br>
&#9;<br>
&#9;return A, center<br>
<br>
<br>
def fit_ellipsoid(points, center=None):<br>
&#9;&quot;&quot;&quot;Строит эллипсоид по набору точек с валидацией и вычислением полуосей.<br>
&#9;<br>
&#9;Эллипсоид задаётся уравнением: (x-c)ᵀ A (x-c) = 1, где:<br>
&#9;- A - положительно определённая матрица (задаёт форму и ориентацию)<br>
&#9;- c - центр эллипсоида<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;points: Массив точек размера (n_points, n_dim).<br>
&#9;&#9;center: Центр эллипсоида размера (n_dim,) или None.<br>
&#9;<br>
&#9;Returns:<br>
&#9;&#9;A: Матрица квадратичной формы размера (n_dim, n_dim)<br>
&#9;&#9;center: Центр эллипсоида размера (n_dim,)<br>
&#9;&#9;radii: Полуоси эллипсоида (собственные значения A⁻¹)<br>
&#9;&#9;axes: Направления осей (собственные векторы A)<br>
&#9;<br>
&#9;Raises:<br>
&#9;&#9;ValueError: Если восстановленная квадрика не является эллипсоидом<br>
&#9;<br>
&#9;Examples:<br>
&#9;&#9;&gt;&gt;&gt; # Точки на сфере радиуса 2<br>
&#9;&#9;&gt;&gt;&gt; theta = np.linspace(0, 2*np.pi, 50)<br>
&#9;&#9;&gt;&gt;&gt; phi = np.linspace(0, np.pi, 50)<br>
&#9;&#9;&gt;&gt;&gt; THETA, PHI = np.meshgrid(theta, phi)<br>
&#9;&#9;&gt;&gt;&gt; X = 2 * np.sin(PHI) * np.cos(THETA)<br>
&#9;&#9;&gt;&gt;&gt; Y = 2 * np.sin(PHI) * np.sin(THETA)<br>
&#9;&#9;&gt;&gt;&gt; Z = 2 * np.cos(PHI)<br>
&#9;&#9;&gt;&gt;&gt; points = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])<br>
&#9;&#9;&gt;&gt;&gt; A, center, radii, axes = fit_ellipsoid(points)<br>
&#9;&#9;&gt;&gt;&gt; radii  # [2, 2, 2]<br>
&#9;&quot;&quot;&quot;<br>
&#9;# Восстанавливаем квадрику универсальным методом<br>
&#9;A, center = fit_quadric(points, center)<br>
&#9;<br>
&#9;# Проверяем, что это именно эллипсоид (все собственные значения &gt; 0)<br>
&#9;eigvals, eigvecs = numpy.linalg.eigh(A)<br>
&#9;<br>
&#9;if numpy.any(eigvals &lt;= 0):<br>
&#9;&#9;raise ValueError(<br>
&#9;&#9;&#9;&quot;Получена не положительно определённая матрица. &quot;<br>
&#9;&#9;&#9;&quot;Точки не лежат на эллипсоиде.&quot;<br>
&#9;&#9;)<br>
&#9;<br>
&#9;# Вычисляем полуоси = sqrt(1/λᵢ), так как (x-c)ᵀA(x-c) = 1 и A = VΛV^T<br>
&#9;radii = 1.0 / numpy.sqrt(eigvals)<br>
&#9;<br>
&#9;# Сортируем по убыванию полуосей (a ≥ b ≥ c)<br>
&#9;sort_idx = numpy.argsort(radii)[::-1]<br>
&#9;radii = radii[sort_idx]<br>
&#9;axes = eigvecs[:, sort_idx]<br>
&#9;<br>
&#9;return A, center, radii, axes<br>
<br>
<br>
def fit_hyperboloid(points, center=None):<br>
&#9;&quot;&quot;&quot;Строит гиперболоид по набору точек с валидацией и анализом типа.<br>
&#9;<br>
&#9;Гиперболоид задаётся уравнением: (x-c)ᵀ A (x-c) = ±1, где:<br>
&#9;- A - матрица со смешанными знаками собственных значений<br>
&#9;- c - центр гиперболоида<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;points: Массив точек размера (n_points, n_dim).<br>
&#9;&#9;center: Центр гиперболоида размера (n_dim,) или None.<br>
&#9;<br>
&#9;Returns:<br>
&#9;&#9;A: Матрица квадратичной формы размера (n_dim, n_dim)<br>
&#9;&#9;center: Центр гиперболоида размера (n_dim,)<br>
&#9;&#9;eigvals: Собственные значения (с разными знаками)<br>
&#9;&#9;eigvecs: Собственные векторы (главные направления)<br>
&#9;&#9;hyperboloid_type: Тип гиперболоида:<br>
&#9;&#9;&#9;- &quot;one-sheet&quot;: однополостный (n-1 положительных, 1 отрицательное)<br>
&#9;&#9;&#9;- &quot;two-sheet&quot;: двуполостный (n-2 положительных, 2 отрицательных)<br>
&#9;&#9;&#9;- &quot;multi-sheet&quot;: многополостный (для размерностей &gt; 3)<br>
&#9;<br>
&#9;Raises:<br>
&#9;&#9;ValueError: Если восстановленная квадрика не является гиперболоидом<br>
&#9;<br>
&#9;Examples:<br>
&#9;&#9;&gt;&gt;&gt; # Однополостный гиперболоид: x²/4 + y²/4 - z² = 1<br>
&#9;&#9;&gt;&gt;&gt; u = np.linspace(0, 2*np.pi, 50)<br>
&#9;&#9;&gt;&gt;&gt; v = np.linspace(-2, 2, 50)<br>
&#9;&#9;&gt;&gt;&gt; U, V = np.meshgrid(u, v)<br>
&#9;&#9;&gt;&gt;&gt; X = 2 * np.cosh(V) * np.cos(U)<br>
&#9;&#9;&gt;&gt;&gt; Y = 2 * np.cosh(V) * np.sin(U)<br>
&#9;&#9;&gt;&gt;&gt; Z = 2 * np.sinh(V)<br>
&#9;&#9;&gt;&gt;&gt; points = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])<br>
&#9;&#9;&gt;&gt;&gt; A, center, eigvals, eigvecs, htype = fit_hyperboloid(points)<br>
&#9;&#9;&gt;&gt;&gt; htype  # &quot;one-sheet&quot;<br>
&#9;&quot;&quot;&quot;<br>
&#9;# Восстанавливаем квадрику универсальным методом<br>
&#9;A, center = fit_quadric(points, center)<br>
&#9;<br>
&#9;# Анализируем собственные значения<br>
&#9;eigvals, eigvecs = numpy.linalg.eigh(A)<br>
&#9;<br>
&#9;pos_count = numpy.sum(eigvals &gt; 0)<br>
&#9;neg_count = numpy.sum(eigvals &lt; 0)<br>
&#9;n_dim = len(eigvals)<br>
&#9;<br>
&#9;# Проверяем, что это гиперболоид (смешанные знаки)<br>
&#9;if pos_count == n_dim or neg_count == n_dim:<br>
&#9;&#9;raise ValueError(<br>
&#9;&#9;&#9;f&quot;Получена квадрика с собственными значениями одного знака. &quot;<br>
&#9;&#9;&#9;f&quot;Это эллипсоид, а не гиперболоид. &quot;<br>
&#9;&#9;&#9;f&quot;Положительных: {pos_count}, отрицательных: {neg_count}&quot;<br>
&#9;&#9;)<br>
&#9;<br>
&#9;if pos_count == 0 or neg_count == 0:<br>
&#9;&#9;raise ValueError(<br>
&#9;&#9;&#9;&quot;Получена вырожденная квадрика. &quot;<br>
&#9;&#9;&#9;&quot;Точки не лежат на гиперболоиде.&quot;<br>
&#9;&#9;)<br>
&#9;<br>
&#9;# Определяем тип гиперболоида<br>
&#9;if neg_count == 1:<br>
&#9;&#9;hyperboloid_type = &quot;one-sheet&quot;<br>
&#9;elif neg_count == 2:<br>
&#9;&#9;hyperboloid_type = &quot;two-sheet&quot;<br>
&#9;else:<br>
&#9;&#9;hyperboloid_type = &quot;multi-sheet&quot;<br>
&#9;<br>
&#9;return A, center, eigvals, eigvecs, hyperboloid_type<br>
<br>
<br>
def fit_paraboloid(points):<br>
&#9;&quot;&quot;&quot;Строит параболоид по набору точек методом линейной регрессии.<br>
&#9;<br>
&#9;Параболоид задаётся уравнением: z = xᵀAx + bᵀx + c, где:<br>
&#9;- A - симметричная матрица размера (n-1, n-1) для координат (x₁,...,xₙ₋₁)<br>
&#9;- b - вектор линейных коэффициентов<br>
&#9;- c - константа<br>
&#9;- z = xₙ - зависимая переменная<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;points: Массив точек размера (n_points, n_dim).<br>
&#9;&#9;&#9;&#9;Последняя координата считается зависимой (высота).<br>
&#9;&#9;&#9;&#9;Минимум n_dim*(n_dim+1)/2 точек.<br>
&#9;<br>
&#9;Returns:<br>
&#9;&#9;A: Матрица квадратичной формы размера (n_dim-1, n_dim-1)<br>
&#9;&#9;b: Вектор линейных коэффициентов размера (n_dim-1,)<br>
&#9;&#9;c: Константа (скаляр)<br>
&#9;&#9;vertex: Вершина параболоида размера (n_dim-1,)<br>
&#9;&#9;eigvals: Собственные значения матрицы A<br>
&#9;&#9;eigvecs: Собственные векторы (главные направления кривизны)<br>
&#9;<br>
&#9;Notes:<br>
&#9;&#9;В отличие от эллипсоида/гиперболоида, параболоид не является<br>
&#9;&#9;центральной квадрикой. Он решается через линейную регрессию,<br>
&#9;&#9;где z явно выражается через остальные координаты.<br>
&#9;&#9;<br>
&#9;&#9;Для 3D: z = ax² + by² + cxy + dx + ey + f<br>
&#9;&#9;<br>
&#9;&#9;Вершина находится из условия ∇z = 0: vertex = -½A⁻¹b<br>
&#9;<br>
&#9;Examples:<br>
&#9;&#9;&gt;&gt;&gt; # Параболоид вращения: z = x² + y²<br>
&#9;&#9;&gt;&gt;&gt; x = np.linspace(-2, 2, 50)<br>
&#9;&#9;&gt;&gt;&gt; y = np.linspace(-2, 2, 50)<br>
&#9;&#9;&gt;&gt;&gt; X, Y = np.meshgrid(x, y)<br>
&#9;&#9;&gt;&gt;&gt; Z = X**2 + Y**2<br>
&#9;&#9;&gt;&gt;&gt; points = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])<br>
&#9;&#9;&gt;&gt;&gt; A, b, c, vertex, eigvals, eigvecs = fit_paraboloid(points)<br>
&#9;&#9;&gt;&gt;&gt; vertex  # ≈ [0, 0]<br>
&#9;&quot;&quot;&quot;<br>
&#9;points = numpy.asarray(points, dtype=float)<br>
&#9;<br>
&#9;if points.ndim != 2:<br>
&#9;&#9;raise ValueError(f&quot;points должен быть 2D массивом, получен {points.ndim}D&quot;)<br>
&#9;<br>
&#9;n_points, n_dim = points.shape<br>
&#9;<br>
&#9;if n_dim &lt; 2:<br>
&#9;&#9;raise ValueError(f&quot;Параболоид требует минимум 2D, получено {n_dim}D&quot;)<br>
&#9;<br>
&#9;# Минимальное количество точек для параболоида<br>
&#9;# Для параметров квадратичной формы без z: (n-1)(n-1+1)/2 + (n-1) + 1<br>
&#9;min_points = (n_dim - 1) * (n_dim) // 2 + (n_dim - 1) + 1<br>
&#9;if n_points &lt; min_points:<br>
&#9;&#9;raise ValueError(<br>
&#9;&#9;&#9;f&quot;Недостаточно точек для параболоида: &quot;<br>
&#9;&#9;&#9;f&quot;нужно минимум {min_points}, получено {n_points}&quot;<br>
&#9;&#9;)<br>
&#9;<br>
&#9;# Выделяем независимые координаты (x₁,...,xₙ₋₁) и зависимую (z = xₙ)<br>
&#9;x_coords = points[:, :-1]  # (n_points, n_dim-1)<br>
&#9;z_coords = points[:, -1]   # (n_points,)<br>
&#9;<br>
&#9;n_indep = n_dim - 1<br>
&#9;<br>
&#9;# Строим матрицу дизайна: [x₁², x₁x₂, x₁x₃, x₂², x₂x₃, x₃², x₁, x₂, x₃, 1]<br>
&#9;columns = []<br>
&#9;<br>
&#9;# Квадратичные члены<br>
&#9;for i in range(n_indep):<br>
&#9;&#9;for j in range(i, n_indep):<br>
&#9;&#9;&#9;if i == j:<br>
&#9;&#9;&#9;&#9;columns.append(x_coords[:, i] ** 2)<br>
&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;columns.append(x_coords[:, i] * x_coords[:, j])<br>
&#9;<br>
&#9;# Линейные члены<br>
&#9;for i in range(n_indep):<br>
&#9;&#9;columns.append(x_coords[:, i])<br>
&#9;<br>
&#9;# Константный член<br>
&#9;columns.append(numpy.ones(n_points))<br>
&#9;<br>
&#9;design_matrix = numpy.column_stack(columns)<br>
&#9;<br>
&#9;# Решаем линейную регрессию: z = design_matrix @ coeffs<br>
&#9;coeffs, residuals, rank, s = numpy.linalg.lstsq(<br>
&#9;&#9;design_matrix, z_coords, rcond=None<br>
&#9;)<br>
&#9;<br>
&#9;# Извлекаем коэффициенты<br>
&#9;n_quad = n_indep * (n_indep + 1) // 2<br>
&#9;<br>
&#9;# Восстанавливаем симметричную матрицу A<br>
&#9;A = numpy.zeros((n_indep, n_indep))<br>
&#9;idx = 0<br>
&#9;for i in range(n_indep):<br>
&#9;&#9;for j in range(i, n_indep):<br>
&#9;&#9;&#9;if i == j:<br>
&#9;&#9;&#9;&#9;A[i, j] = coeffs[idx]<br>
&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;A[i, j] = coeffs[idx]<br>
&#9;&#9;&#9;&#9;A[j, i] = coeffs[idx]<br>
&#9;&#9;&#9;idx += 1<br>
&#9;<br>
&#9;# Линейные коэффициенты<br>
&#9;b = coeffs[n_quad:n_quad + n_indep]<br>
&#9;<br>
&#9;# Константа<br>
&#9;c = coeffs[n_quad + n_indep]<br>
&#9;<br>
&#9;# Вычисляем вершину параболоида: точку экстремума<br>
&#9;# ∇z = 2Ax + b = 0 =&gt; x = -½A⁻¹b<br>
&#9;try:<br>
&#9;&#9;A_inv = numpy.linalg.inv(A)<br>
&#9;&#9;vertex = -0.5 * A_inv @ b<br>
&#9;except numpy.linalg.LinAlgError:<br>
&#9;&#9;# Вырожденный случай (например, цилиндр)<br>
&#9;&#9;vertex = numpy.zeros(n_indep)<br>
&#9;&#9;vertex[:] = numpy.nan<br>
&#9;<br>
&#9;# Анализируем кривизну через собственные значения<br>
&#9;eigvals, eigvecs = numpy.linalg.eigh(A)<br>
&#9;<br>
&#9;return A, b, c, vertex, eigvals, eigvecs<br>
<br>
<br>
def _fit_quadric_fixed_center(points, center):<br>
&#9;&quot;&quot;&quot;Подгоняет квадрику с заданным центром.<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;points: Массив точек размера (n_points, n_dim)<br>
&#9;&#9;center: Центр квадрики размера (n_dim,)<br>
&#9;<br>
&#9;Returns:<br>
&#9;&#9;Матрица A размера (n_dim, n_dim)<br>
&#9;&quot;&quot;&quot;<br>
&#9;n_points, n_dim = points.shape<br>
&#9;<br>
&#9;# Сдвигаем точки к центру<br>
&#9;points_centered = points - center<br>
&#9;<br>
&#9;# Строим матрицу дизайна для квадратичной формы xᵀAx = 1<br>
&#9;design_matrix = _build_quadratic_design_matrix(points_centered)<br>
&#9;<br>
&#9;# Решаем систему: design_matrix @ coeffs = 1<br>
&#9;coeffs, residuals, rank, s = numpy.linalg.lstsq(<br>
&#9;&#9;design_matrix, numpy.ones(n_points), rcond=None<br>
&#9;)<br>
&#9;<br>
&#9;# Восстанавливаем симметричную матрицу A из коэффициентов<br>
&#9;A = _coeffs_to_matrix(coeffs, n_dim)<br>
&#9;<br>
&#9;return A<br>
<br>
<br>
def _fit_quadric_auto_center(points):<br>
&#9;&quot;&quot;&quot;Подгоняет квадрику с автоматическим определением центра.<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;points: Массив точек размера (n_points, n_dim)<br>
&#9;<br>
&#9;Returns:<br>
&#9;&#9;A: Матрица размера (n_dim, n_dim)<br>
&#9;&#9;center: Центр размера (n_dim,)<br>
&#9;&quot;&quot;&quot;<br>
&#9;n_points, n_dim = points.shape<br>
&#9;<br>
&#9;# Строим полную матрицу дизайна: [квадратичные, линейные, константа]<br>
&#9;design_matrix = _build_full_design_matrix(points)<br>
&#9;<br>
&#9;# Решаем однородную систему с ограничением ||coeffs|| = 1<br>
&#9;# Используем SVD: решение = правый сингулярный вектор для минимального σ<br>
&#9;u, s, vh = numpy.linalg.svd(design_matrix, full_matrices=True)<br>
&#9;coeffs = vh[-1, :]<br>
&#9;<br>
&#9;# Извлекаем компоненты<br>
&#9;n_quad = n_dim * (n_dim + 1) // 2<br>
&#9;A = _coeffs_to_matrix(coeffs[:n_quad], n_dim)<br>
&#9;b = coeffs[n_quad:n_quad + n_dim]<br>
&#9;d = coeffs[n_quad + n_dim]<br>
&#9;<br>
&#9;# SVD может дать решение с произвольным знаком<br>
&#9;# Нормализуем так, чтобы след матрицы был положительным<br>
&#9;if numpy.trace(A) &lt; 0:<br>
&#9;&#9;A = -A<br>
&#9;&#9;b = -b<br>
&#9;&#9;d = -d<br>
&#9;<br>
&#9;# Проверяем невырожденность<br>
&#9;eigvals = numpy.linalg.eigvalsh(A)<br>
&#9;if numpy.all(numpy.abs(eigvals) &lt; 1e-10):<br>
&#9;&#9;raise ValueError(<br>
&#9;&#9;&#9;&quot;Получена вырожденная матрица. &quot;<br>
&#9;&#9;&#9;&quot;Точки не лежат на центральной квадрике.&quot;<br>
&#9;&#9;)<br>
&#9;<br>
&#9;# Находим центр: c = -½A⁻¹b<br>
&#9;try:<br>
&#9;&#9;A_inv = numpy.linalg.inv(A)<br>
&#9;&#9;center = -0.5 * A_inv @ b<br>
&#9;except numpy.linalg.LinAlgError:<br>
&#9;&#9;raise ValueError(<br>
&#9;&#9;&#9;&quot;Не удалось найти центр квадрики. &quot;<br>
&#9;&#9;&#9;&quot;Возможно, точки лежат на параболоиде или вырожденной поверхности.&quot;<br>
&#9;&#9;)<br>
&#9;<br>
&#9;# Нормализуем к канонической форме (x-c)ᵀA(x-c) = ±1<br>
&#9;k = -(center @ A @ center + b @ center + d)<br>
&#9;<br>
&#9;if numpy.abs(k) &lt; 1e-10:<br>
&#9;&#9;raise ValueError(&quot;Некорректная нормализация. Проверьте входные данные.&quot;)<br>
&#9;<br>
&#9;A = A / k<br>
&#9;<br>
&#9;return A, center<br>
<br>
<br>
def _build_quadratic_design_matrix(points):<br>
&#9;&quot;&quot;&quot;Строит матрицу дизайна для квадратичных членов.<br>
&#9;<br>
&#9;Для каждой точки: [x², xy, xz, y², yz, z², ...] (верхний треугольник).<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;points: Массив точек размера (n_points, n_dim)<br>
&#9;<br>
&#9;Returns:<br>
&#9;&#9;Матрица дизайна размера (n_points, n_dim*(n_dim+1)/2)<br>
&#9;&quot;&quot;&quot;<br>
&#9;n_points, n_dim = points.shape<br>
&#9;columns = []<br>
&#9;<br>
&#9;for i in range(n_dim):<br>
&#9;&#9;for j in range(i, n_dim):<br>
&#9;&#9;&#9;if i == j:<br>
&#9;&#9;&#9;&#9;# Диагональные элементы: x², y², z²<br>
&#9;&#9;&#9;&#9;columns.append(points[:, i] ** 2)<br>
&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;# Внедиагональные: 2*xy, 2*xz, 2*yz (множитель 2 для симметрии)<br>
&#9;&#9;&#9;&#9;columns.append(2 * points[:, i] * points[:, j])<br>
&#9;<br>
&#9;return numpy.column_stack(columns)<br>
<br>
<br>
def _build_full_design_matrix(points):<br>
&#9;&quot;&quot;&quot;Строит полную матрицу дизайна: квадратичные + линейные + константа.<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;points: Массив точек размера (n_points, n_dim)<br>
&#9;<br>
&#9;Returns:<br>
&#9;&#9;Матрица дизайна размера (n_points, n_dim*(n_dim+3)/2 + 1)<br>
&#9;&quot;&quot;&quot;<br>
&#9;n_points, n_dim = points.shape<br>
&#9;<br>
&#9;# Квадратичные члены<br>
&#9;quad_matrix = _build_quadratic_design_matrix(points)<br>
&#9;<br>
&#9;# Линейные члены<br>
&#9;linear_columns = [points[:, i] for i in range(n_dim)]<br>
&#9;<br>
&#9;# Константный член<br>
&#9;const_column = [numpy.ones(n_points)]<br>
&#9;<br>
&#9;return numpy.column_stack([quad_matrix] + linear_columns + const_column)<br>
<br>
<br>
def _coeffs_to_matrix(coeffs, n_dim):<br>
&#9;&quot;&quot;&quot;Восстанавливает симметричную матрицу из коэффициентов верхнего треугольника.<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;coeffs: Коэффициенты размера (n_dim*(n_dim+1)/2,)<br>
&#9;&#9;n_dim: Размерность матрицы<br>
&#9;<br>
&#9;Returns:<br>
&#9;&#9;Симметричная матрица размера (n_dim, n_dim)<br>
&#9;&quot;&quot;&quot;<br>
&#9;A = numpy.zeros((n_dim, n_dim))<br>
&#9;idx = 0<br>
&#9;<br>
&#9;for i in range(n_dim):<br>
&#9;&#9;for j in range(i, n_dim):<br>
&#9;&#9;&#9;if i == j:<br>
&#9;&#9;&#9;&#9;A[i, j] = coeffs[idx]<br>
&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;A[i, j] = coeffs[idx]<br>
&#9;&#9;&#9;&#9;A[j, i] = coeffs[idx]<br>
&#9;&#9;&#9;idx += 1<br>
&#9;<br>
&#9;return A<br>
<br>
<br>
def ellipsoid_equation(A, center):<br>
&#9;&quot;&quot;&quot;Форматирует уравнение эллипсоида в читаемую строку.<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;A: Матрица квадратичной формы размера (n_dim, n_dim)<br>
&#9;&#9;center: Центр эллипсоида размера (n_dim,)<br>
&#9;<br>
&#9;Returns:<br>
&#9;&#9;Строковое представление уравнения<br>
&#9;&quot;&quot;&quot;<br>
&#9;n_dim = len(center)<br>
&#9;coord_names = ['x', 'y', 'z', 'w'] + [f'x_{i}' for i in range(4, n_dim)]<br>
&#9;<br>
&#9;terms = []<br>
&#9;for i in range(n_dim):<br>
&#9;&#9;ci = center[i]<br>
&#9;&#9;coord = coord_names[i]<br>
&#9;&#9;if abs(ci) &gt; 1e-10:<br>
&#9;&#9;&#9;terms.append(f&quot;({coord} - {ci:.3g})&quot;)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;terms.append(coord)<br>
&#9;<br>
&#9;if n_dim &lt;= 3:<br>
&#9;&#9;return f&quot;(x-c)ᵀ A (x-c) = 1, где c = {center}&quot;<br>
&#9;else:<br>
&#9;&#9;return f&quot;Эллипсоид в R^{n_dim} с центром {center}&quot;<br>
<br>
<br>
def _gamma_half_integer(n):<br>
&#9;&quot;&quot;&quot;Вычисляет Γ(n/2 + 1) для натуральных n.<br>
&#9;<br>
&#9;Специализированная функция для вычисления гамма-функции в точках<br>
&#9;вида n/2 + 1, где n — натуральное число. Используется для формулы<br>
&#9;объёма n-мерной сферы/эллипсоида.<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;n: Натуральное число (размерность пространства)<br>
&#9;<br>
&#9;Returns:<br>
&#9;&#9;Значение Γ(n/2 + 1)<br>
&#9;<br>
&#9;Notes:<br>
&#9;&#9;Для чётных n: Γ(n/2 + 1) = (n/2)!<br>
&#9;&#9;Для нечётных n: Γ(n/2 + 1) = Γ(0.5) * ∏(k + 0.5) для k=0..m,<br>
&#9;&#9;&#9;&#9;&#9;&#9;где m = (n-1)/2 и Γ(0.5) = √π<br>
&#9;&#9;<br>
&#9;&#9;Примеры:<br>
&#9;&#9;- n=2: Γ(2) = 1! = 1<br>
&#9;&#9;- n=3: Γ(2.5) = 1.5 × 0.5 × √π ≈ 1.329<br>
&#9;&#9;- n=4: Γ(3) = 2! = 2<br>
&#9;&quot;&quot;&quot;<br>
&#9;if n % 2 == 0:<br>
&#9;&#9;# n чётное: Γ(k+1) = k! для k = n/2<br>
&#9;&#9;k = n // 2<br>
&#9;&#9;return float(math.factorial(k))<br>
&#9;else:<br>
&#9;&#9;# n нечётное: n = 2m + 1, n/2 + 1 = m + 1.5<br>
&#9;&#9;# Γ(m + 1.5) = Γ(0.5) * ∏(k + 0.5) для k = 0..m<br>
&#9;&#9;# где Γ(0.5) = sqrt(π)<br>
&#9;&#9;m = (n - 1) // 2<br>
&#9;&#9;gamma_val = numpy.sqrt(numpy.pi)<br>
&#9;&#9;for k in range(m + 1):<br>
&#9;&#9;&#9;gamma_val *= (k + 0.5)<br>
&#9;&#9;return gamma_val<br>
<br>
<br>
def ellipsoid_volume(radii):<br>
&#9;&quot;&quot;&quot;Вычисляет объём эллипсоида по полуосям.<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;radii: Полуоси эллипсоида размера (n_dim,)<br>
&#9;<br>
&#9;Returns:<br>
&#9;&#9;Объём эллипсоида<br>
&#9;<br>
&#9;Notes:<br>
&#9;&#9;V = (π^(n/2) / Γ(n/2 + 1)) * ∏rᵢ<br>
&#9;&#9;<br>
&#9;&#9;Для малых размерностей:<br>
&#9;&#9;- 1D: 2r (длина отрезка)<br>
&#9;&#9;- 2D: πab (площадь эллипса)<br>
&#9;&#9;- 3D: (4/3)πabc (объём эллипсоида)<br>
&#9;&quot;&quot;&quot;<br>
&#9;radii = numpy.asarray(radii)<br>
&#9;n_dim = len(radii)<br>
&#9;<br>
&#9;# Вычисляем Γ(n/2 + 1) для размерности n<br>
&#9;gamma_val = _gamma_half_integer(n_dim)<br>
&#9;<br>
&#9;# V = (π^(n/2) / Γ(n/2 + 1)) * ∏rᵢ<br>
&#9;half_n = n_dim / 2.0<br>
&#9;volume = (numpy.pi ** half_n / gamma_val) * numpy.prod(radii)<br>
&#9;<br>
&#9;return volume<br>
<br>
<br>
def evaluate_ellipsoid(points, A, center):<br>
&#9;&quot;&quot;&quot;Вычисляет значения квадратичной формы эллипсоида в точках.<br>
&#9;<br>
&#9;Для эллипсоида (x-c)ᵀA(x-c) = 1 вычисляет (x-c)ᵀA(x-c) для каждой точки.<br>
&#9;Значения:<br>
&#9;- &lt; 1: точка внутри эллипсоида<br>
&#9;- = 1: точка на поверхности<br>
&#9;- &gt; 1: точка снаружи<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;points: Массив точек размера (n_points, n_dim)<br>
&#9;&#9;A: Матрица квадратичной формы размера (n_dim, n_dim)<br>
&#9;&#9;center: Центр эллипсоида размера (n_dim,)<br>
&#9;<br>
&#9;Returns:<br>
&#9;&#9;Массив значений размера (n_points,)<br>
&#9;&quot;&quot;&quot;<br>
&#9;points = numpy.asarray(points, dtype=float)<br>
&#9;center = numpy.asarray(center, dtype=float)<br>
&#9;A = numpy.asarray(A, dtype=float)<br>
&#9;<br>
&#9;# Центрируем точки<br>
&#9;points_centered = points - center<br>
&#9;<br>
&#9;# Вычисляем квадратичную форму: (x-c)ᵀA(x-c)<br>
&#9;# Эффективно: sum((A @ p) * p) для каждой точки<br>
&#9;values = numpy.sum((points_centered @ A) * points_centered, axis=1)<br>
&#9;<br>
&#9;return values<br>
<br>
<br>
def ellipsoid_contains(points, A, center, tol=1e-10):<br>
&#9;&quot;&quot;&quot;Проверяет, лежат ли точки внутри или на эллипсоиде.<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;points: Массив точек размера (n_points, n_dim)<br>
&#9;&#9;A: Матрица квадратичной формы размера (n_dim, n_dim)<br>
&#9;&#9;center: Центр эллипсоида размера (n_dim,)<br>
&#9;&#9;tol: Допуск для точек на границе<br>
&#9;<br>
&#9;Returns:<br>
&#9;&#9;Булев массив размера (n_points,): True если точка внутри/на эллипсоиде<br>
&#9;&quot;&quot;&quot;<br>
&#9;values = evaluate_ellipsoid(points, A, center)<br>
&#9;return values &lt;= (1.0 + tol)<br>
<br>
<!-- END SCAT CODE -->
</body>
</html>
