<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/linalg/subspaces.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import numpy<br>
<br>
<br>
def _ensure_inexact(A):<br>
&#9;&quot;&quot;&quot;Конвертирует целочисленные массивы в float, сохраняя float/complex типы.&quot;&quot;&quot;<br>
&#9;A = numpy.asarray(A)<br>
&#9;if not numpy.issubdtype(A.dtype, numpy.inexact):<br>
&#9;&#9;# Конвертируем целые числа в float64<br>
&#9;&#9;return numpy.asarray(A, dtype=float)<br>
&#9;# Оставляем float32/float64/complex как есть<br>
&#9;return A<br>
<br>
<br>
def nullspace_projector(A):<br>
&#9;&quot;&quot;&quot;Возвращает матрицу ортогонального проектора на нуль-пространство матрицы A.<br>
&#9;<br>
&#9;Проектор P обладает свойствами:<br>
&#9;- A @ P = 0 (проекция попадает в нуль-пространство)<br>
&#9;- P @ P = P (идемпотентность)<br>
&#9;- P.T = P (для вещественных матриц - симметричность)<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;A: Матрица размера (m, n)<br>
&#9;&#9;<br>
&#9;Returns:<br>
&#9;&#9;Матрица проектора размера (n, n)<br>
&#9;&#9;<br>
&#9;Notes:<br>
&#9;&#9;Для проекции вектора v на нуль-пространство: v_proj = P @ v<br>
&#9;&#9;Использует SVD-разложение для оптимальной производительности.<br>
&#9;&quot;&quot;&quot;<br>
&#9;A = _ensure_inexact(A)<br>
&#9;u, s, vh = numpy.linalg.svd(A, full_matrices=True)<br>
&#9;<br>
&#9;# Определяем ранг матрицы<br>
&#9;tol = max(A.shape) * numpy.finfo(A.dtype).eps * s[0] if s.size &gt; 0 else 0<br>
&#9;rank = numpy.sum(s &gt; tol)<br>
&#9;<br>
&#9;# Базис нуль-пространства = правые сингулярные векторы для нулевых сингулярных чисел<br>
&#9;null_basis = vh[rank:].T.conj()<br>
&#9;<br>
&#9;# Проектор = базис @ базис.T<br>
&#9;if null_basis.size &gt; 0:<br>
&#9;&#9;return null_basis @ null_basis.T.conj()<br>
&#9;else:<br>
&#9;&#9;# Нуль-пространство пустое - возвращаем нулевой проектор<br>
&#9;&#9;return numpy.zeros((A.shape[1], A.shape[1]), dtype=A.dtype)<br>
<br>
<br>
def nullspace_basis_svd(A, rtol=None, atol=None):<br>
&#9;&quot;&quot;&quot;Ортонормированный базис ker(A), полученный через SVD A = U Σ V^H.<br>
<br>
&#9;Правые сингулярные векторы, соответствующие нулевым σ, образуют базис<br>
&#9;нуль-пространства. В реализации отбрасываются σ ниже заданного порога.<br>
<br>
&#9;Args:<br>
&#9;&#9;A: Матрица размера (m, n)<br>
&#9;&#9;rtol: Относительный порог для сингулярных чисел (≈ eps · max(m, n)).<br>
&#9;&#9;atol: Абсолютный порог (если задан, имеет приоритет над rtol).<br>
<br>
&#9;Returns:<br>
&#9;&#9;Матрица (n, k) с ортонормированными столбцами basis, где A @ basis = 0.<br>
&#9;&#9;Если ker(A) тривиально, возвращается массив формы (n, 0).<br>
&#9;&quot;&quot;&quot;<br>
&#9;A = _ensure_inexact(A)<br>
&#9;u, s, vh = numpy.linalg.svd(A, full_matrices=True)<br>
<br>
&#9;if atol is not None:<br>
&#9;&#9;tol = atol<br>
&#9;else:<br>
&#9;&#9;if rtol is None:<br>
&#9;&#9;&#9;rtol = max(A.shape) * numpy.finfo(A.dtype).eps<br>
&#9;&#9;tol = rtol * s[0] if s.size &gt; 0 else rtol<br>
<br>
&#9;rank = numpy.sum(s &gt; tol)<br>
&#9;null_basis = vh[rank:].T.conj()<br>
<br>
&#9;if null_basis.size == 0:<br>
&#9;&#9;return numpy.zeros((A.shape[1], 0), dtype=A.dtype)<br>
<br>
&#9;return null_basis<br>
<br>
<br>
def nullspace_basis_qr(A, rtol=None, atol=None):<br>
&#9;&quot;&quot;&quot;Ортонормированный базис ker(A) по формуле A^T = Q R (полный QR).<br>
<br>
&#9;Если r = rank(A), то строки A лежат в span(Q[:, :r]) и<br>
&#9;ker(A) = (rowspace(A))^⊥ = span(Q[:, r:]). Хвостовые столбцы Q уже<br>
&#9;ортонормированы и задают искомый базис.<br>
<br>
&#9;Args:<br>
&#9;&#9;A: Матрица размера (m, n)<br>
&#9;&#9;rtol: Относительный порог для диагонали R.<br>
&#9;&#9;atol: Абсолютный порог (если задан, имеет приоритет).<br>
<br>
&#9;Returns:<br>
&#9;&#9;Матрица (n, k) с ортонормированными столбцами ker(A).<br>
&#9;&#9;Если дополнение тривиально, возвращается массив формы (n, 0).<br>
&#9;&quot;&quot;&quot;<br>
&#9;A = _ensure_inexact(A)<br>
&#9;m, n = A.shape<br>
<br>
&#9;if n == 0:<br>
&#9;&#9;return numpy.zeros((0, 0), dtype=A.dtype)<br>
<br>
&#9;Q, R = numpy.linalg.qr(A.T, mode=&quot;complete&quot;)<br>
&#9;diag_len = min(n, m)<br>
<br>
&#9;if diag_len == 0:<br>
&#9;&#9;rank = 0<br>
&#9;else:<br>
&#9;&#9;diag = numpy.abs(numpy.diag(R[:diag_len, :diag_len]))<br>
&#9;&#9;max_diag = diag.max() if diag.size &gt; 0 else 0.0<br>
<br>
&#9;&#9;if atol is not None:<br>
&#9;&#9;&#9;tol = atol<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;if rtol is None:<br>
&#9;&#9;&#9;&#9;rtol = max(m, n) * numpy.finfo(A.dtype).eps<br>
&#9;&#9;&#9;tol = rtol * max_diag if max_diag &gt; 0 else rtol<br>
<br>
&#9;&#9;rank = int(numpy.sum(diag &gt; tol))<br>
<br>
&#9;return Q[:, rank:]<br>
<br>
<br>
def nullspace_basis(A, rtol=None, atol=None, method=&quot;svd&quot;):<br>
&#9;&quot;&quot;&quot;Возвращает ортонормированный базис ker(A) с выбранным алгоритмом.<br>
<br>
&#9;Args:<br>
&#9;&#9;A: Матрица размера (m, n)<br>
&#9;&#9;rtol: Относительный порог толеранса.<br>
&#9;&#9;atol: Абсолютный порог толеранса.<br>
&#9;&#9;method: 'svd' (устойчивее) или 'qr' (быстрее для узких матриц).<br>
<br>
&#9;Returns:<br>
&#9;&#9;Матрица (n, k), столбцы которой образуют базис нуль-пространства.<br>
<br>
&#9;Raises:<br>
&#9;&#9;ValueError: если указан неподдерживаемый method.<br>
&#9;&quot;&quot;&quot;<br>
&#9;if method is None:<br>
&#9;&#9;method = &quot;svd&quot;<br>
<br>
&#9;if method == &quot;svd&quot;:<br>
&#9;&#9;return nullspace_basis_svd(A, rtol=rtol, atol=atol)<br>
&#9;if method == &quot;qr&quot;:<br>
&#9;&#9;return nullspace_basis_qr(A, rtol=rtol, atol=atol)<br>
<br>
&#9;raise ValueError(f&quot;Unsupported nullspace method '{method}'. Use 'svd' or 'qr'.&quot;)<br>
<br>
<br>
def rowspace_projector(A):<br>
&#9;&quot;&quot;&quot;Возвращает матрицу ортогонального проектора на пространство строк матрицы A.<br>
&#9;<br>
&#9;Пространство строк (row space) - это ортогональное дополнение к нуль-пространству.<br>
&#9;Проектор P обладает свойствами:<br>
&#9;- P @ v лежит в пространстве строк для любого v<br>
&#9;- P + nullspace_projector(A) = I (дополнение)<br>
&#9;- P @ P = P (идемпотентность)<br>
&#9;- P.T = P (для вещественных матриц - симметричность)<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;A: Матрица размера (m, n)<br>
&#9;&#9;<br>
&#9;Returns:<br>
&#9;&#9;Матрица проектора размера (n, n)<br>
&#9;&#9;<br>
&#9;Notes:<br>
&#9;&#9;Для проекции вектора v на пространство строк: v_proj = P @ v<br>
&#9;&#9;rowspace_projector(A) = I - nullspace_projector(A)<br>
&#9;&quot;&quot;&quot;<br>
&#9;A = _ensure_inexact(A)<br>
&#9;u, s, vh = numpy.linalg.svd(A, full_matrices=True)<br>
&#9;<br>
&#9;# Определяем ранг матрицы<br>
&#9;tol = max(A.shape) * numpy.finfo(A.dtype).eps * s[0] if s.size &gt; 0 else 0<br>
&#9;rank = numpy.sum(s &gt; tol)<br>
&#9;<br>
&#9;# Базис пространства строк = правые сингулярные векторы для ненулевых σ<br>
&#9;row_basis = vh[:rank].T.conj()<br>
&#9;<br>
&#9;# Проектор = базис @ базис.T<br>
&#9;if row_basis.size &gt; 0:<br>
&#9;&#9;return row_basis @ row_basis.T.conj()<br>
&#9;else:<br>
&#9;&#9;# Пространство строк пустое - возвращаем нулевой проектор<br>
&#9;&#9;return numpy.zeros((A.shape[1], A.shape[1]), dtype=A.dtype)<br>
<br>
<br>
def rowspace_basis(A, rtol=None):<br>
&#9;&quot;&quot;&quot;Возвращает ортонормированный базис пространства строк матрицы A.<br>
&#9;<br>
&#9;Пространство строк (row space) состоит из всех линейных комбинаций строк A.<br>
&#9;Это ортогональное дополнение к нуль-пространству: rowspace ⊕ nullspace = R^n.<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;A: Матрица размера (m, n)<br>
&#9;&#9;rtol: Относительный порог для определения нулевых сингулярных чисел.<br>
&#9;&#9;&#9;По умолчанию: max(m, n) * машинная_точность * max(сингулярное_число)<br>
&#9;&#9;<br>
&#9;Returns:<br>
&#9;&#9;Матрица размера (n, k) где k = rank(A) - размерность пространства строк.<br>
&#9;&#9;Столбцы образуют ортонормированный базис пространства строк.<br>
&#9;&#9;Если rank(A) = 0, возвращает массив формы (n, 0).<br>
&#9;<br>
&#9;Notes:<br>
&#9;&#9;- Использует SVD-разложение для численной устойчивости<br>
&#9;&#9;- Размерность пространства строк = rank(A)<br>
&#9;&#9;- Векторы базиса ортонормированы: basis.T @ basis = I<br>
&#9;&#9;- Для получения проектора: P = basis @ basis.T<br>
&#9;&#9;- Дополнение: rowspace_basis ⊕ nullspace_basis = полный базис R^n<br>
&#9;<br>
&#9;Examples:<br>
&#9;&#9;&gt;&gt;&gt; A = np.array([[1, 2, 3], [2, 4, 6]])  # Ранг 1<br>
&#9;&#9;&gt;&gt;&gt; R = rowspace_basis(A)<br>
&#9;&#9;&gt;&gt;&gt; R.shape  # (3, 1) - базис из 1 вектора<br>
&#9;&#9;&gt;&gt;&gt; N = nullspace_basis(A)<br>
&#9;&#9;&gt;&gt;&gt; N.shape  # (3, 2) - дополнение<br>
&#9;&quot;&quot;&quot;<br>
&#9;A = _ensure_inexact(A)<br>
&#9;u, s, vh = numpy.linalg.svd(A, full_matrices=True)<br>
&#9;<br>
&#9;# Определяем порог для малых сингулярных чисел<br>
&#9;if rtol is None:<br>
&#9;&#9;rtol = max(A.shape) * numpy.finfo(A.dtype).eps<br>
&#9;<br>
&#9;tol = rtol * s[0] if s.size &gt; 0 else rtol<br>
&#9;<br>
&#9;# Ранг матрицы = количество сингулярных чисел больше порога<br>
&#9;rank = numpy.sum(s &gt; tol)<br>
&#9;<br>
&#9;# Пространство строк = правые сингулярные векторы соответствующие ненулевым σ<br>
&#9;# Берём строки vh с индексами [:rank] и транспонируем<br>
&#9;row_basis = vh[:rank].T.conj()<br>
&#9;<br>
&#9;return row_basis<br>
<br>
<br>
def colspace_projector(A):<br>
&#9;&quot;&quot;&quot;Возвращает матрицу ортогонального проектора на пространство столбцов матрицы A.<br>
&#9;<br>
&#9;Пространство столбцов (column space, range) - это образ отображения A.<br>
&#9;Проектор P обладает свойствами:<br>
&#9;- P @ b лежит в colspace для любого b<br>
&#9;- P + left_nullspace_projector(A) = I (дополнение)<br>
&#9;- P @ P = P (идемпотентность)<br>
&#9;- P.T = P (для вещественных матриц - симметричность)<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;A: Матрица размера (m, n)<br>
&#9;&#9;<br>
&#9;Returns:<br>
&#9;&#9;Матрица проектора размера (m, m)<br>
&#9;&#9;<br>
&#9;Notes:<br>
&#9;&#9;Для проекции вектора b на пространство столбцов: b_proj = P @ b<br>
&#9;&#9;Если Ax = b несовместна, то Ax = P @ b всегда разрешима.<br>
&#9;&#9;Работает в пространстве значений R^m.<br>
&#9;&quot;&quot;&quot;<br>
&#9;A = _ensure_inexact(A)<br>
&#9;u, s, vh = numpy.linalg.svd(A, full_matrices=True)<br>
&#9;<br>
&#9;# Определяем ранг матрицы<br>
&#9;tol = max(A.shape) * numpy.finfo(A.dtype).eps * s[0] if s.size &gt; 0 else 0<br>
&#9;rank = numpy.sum(s &gt; tol)<br>
&#9;<br>
&#9;# Базис пространства столбцов = левые сингулярные векторы для ненулевых σ<br>
&#9;col_basis = u[:, :rank]<br>
&#9;<br>
&#9;# Проектор = базис @ базис.T<br>
&#9;if col_basis.size &gt; 0:<br>
&#9;&#9;return col_basis @ col_basis.T.conj()<br>
&#9;else:<br>
&#9;&#9;# Пространство столбцов пустое - возвращаем нулевой проектор<br>
&#9;&#9;return numpy.zeros((A.shape[0], A.shape[0]), dtype=A.dtype)<br>
<br>
<br>
def colspace_basis(A, rtol=None):<br>
&#9;&quot;&quot;&quot;Возвращает ортонормированный базис пространства столбцов матрицы A.<br>
&#9;<br>
&#9;Пространство столбцов (column space, range, образ) состоит из всех векторов вида A @ x.<br>
&#9;Это ортогональное дополнение к левому нуль-пространству: colspace ⊕ left_nullspace = R^m.<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;A: Матрица размера (m, n)<br>
&#9;&#9;rtol: Относительный порог для определения нулевых сингулярных чисел.<br>
&#9;&#9;&#9;По умолчанию: max(m, n) * машинная_точность * max(сингулярное_число)<br>
&#9;&#9;<br>
&#9;Returns:<br>
&#9;&#9;Матрица размера (m, k) где k = rank(A) - размерность пространства столбцов.<br>
&#9;&#9;Столбцы образуют ортонормированный базис пространства столбцов.<br>
&#9;&#9;Если rank(A) = 0, возвращает массив формы (m, 0).<br>
&#9;<br>
&#9;Notes:<br>
&#9;&#9;- Использует SVD-разложение для численной устойчивости<br>
&#9;&#9;- Размерность пространства столбцов = rank(A)<br>
&#9;&#9;- Векторы базиса ортонормированы: basis.T @ basis = I<br>
&#9;&#9;- Для получения проектора: P = basis @ basis.T<br>
&#9;&#9;- Работает в пространстве значений R^m<br>
&#9;&#9;- Эквивалент scipy.linalg.orth(A)<br>
&#9;<br>
&#9;Examples:<br>
&#9;&#9;&gt;&gt;&gt; A = np.array([[1, 0], [2, 0], [3, 0]])  # Ранг 1<br>
&#9;&#9;&gt;&gt;&gt; C = colspace_basis(A)<br>
&#9;&#9;&gt;&gt;&gt; C.shape  # (3, 1) - базис из 1 вектора<br>
&#9;&#9;&gt;&gt;&gt; # Любой вектор A @ x лежит в span(C)<br>
&#9;&quot;&quot;&quot;<br>
&#9;A = _ensure_inexact(A)<br>
&#9;u, s, vh = numpy.linalg.svd(A, full_matrices=True)<br>
&#9;<br>
&#9;# Определяем порог для малых сингулярных чисел<br>
&#9;if rtol is None:<br>
&#9;&#9;rtol = max(A.shape) * numpy.finfo(A.dtype).eps<br>
&#9;<br>
&#9;tol = rtol * s[0] if s.size &gt; 0 else rtol<br>
&#9;<br>
&#9;# Ранг матрицы = количество сингулярных чисел больше порога<br>
&#9;rank = numpy.sum(s &gt; tol)<br>
&#9;<br>
&#9;# Пространство столбцов = левые сингулярные векторы соответствующие ненулевым σ<br>
&#9;col_basis = u[:, :rank]<br>
&#9;<br>
&#9;return col_basis<br>
<br>
<br>
def left_nullspace_projector(A):<br>
&#9;&quot;&quot;&quot;Возвращает матрицу ортогонального проектора на левое нуль-пространство матрицы A.<br>
&#9;<br>
&#9;Левое нуль-пространство состоит из векторов y таких, что A^T @ y = 0.<br>
&#9;Это ортогональное дополнение к пространству столбцов.<br>
&#9;Проектор P обладает свойствами:<br>
&#9;- A^T @ P = 0 (эквивалентно: P @ A = 0)<br>
&#9;- P + colspace_projector(A) = I (дополнение)<br>
&#9;- P @ P = P (идемпотентность)<br>
&#9;- P.T = P (для вещественных матриц - симметричность)<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;A: Матрица размера (m, n)<br>
&#9;&#9;<br>
&#9;Returns:<br>
&#9;&#9;Матрица проектора размера (m, m)<br>
&#9;&#9;<br>
&#9;Notes:<br>
&#9;&#9;Для проекции вектора b на левое нуль-пространство: b_proj = P @ b<br>
&#9;&#9;left_nullspace(A) = nullspace(A^T)<br>
&#9;&#9;Работает в пространстве значений R^m.<br>
&#9;&quot;&quot;&quot;<br>
&#9;A = _ensure_inexact(A)<br>
&#9;u, s, vh = numpy.linalg.svd(A, full_matrices=True)<br>
&#9;<br>
&#9;# Определяем ранг матрицы<br>
&#9;tol = max(A.shape) * numpy.finfo(A.dtype).eps * s[0] if s.size &gt; 0 else 0<br>
&#9;rank = numpy.sum(s &gt; tol)<br>
&#9;<br>
&#9;# Базис левого нуль-пространства = левые сингулярные векторы для нулевых σ<br>
&#9;left_null_basis = u[:, rank:]<br>
&#9;<br>
&#9;# Проектор = базис @ базис.T<br>
&#9;if left_null_basis.size &gt; 0:<br>
&#9;&#9;return left_null_basis @ left_null_basis.T.conj()<br>
&#9;else:<br>
&#9;&#9;# Левое нуль-пространство пустое - возвращаем нулевой проектор<br>
&#9;&#9;return numpy.zeros((A.shape[0], A.shape[0]), dtype=A.dtype)<br>
<br>
<br>
def left_nullspace_basis(A, rtol=None):<br>
&#9;&quot;&quot;&quot;Возвращает ортонормированный базис левого нуль-пространства матрицы A.<br>
&#9;<br>
&#9;Левое нуль-пространство состоит из векторов y таких, что A^T @ y = 0.<br>
&#9;Это ортогональное дополнение к пространству столбцов: left_nullspace ⊕ colspace = R^m.<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;A: Матрица размера (m, n)<br>
&#9;&#9;rtol: Относительный порог для определения нулевых сингулярных чисел.<br>
&#9;&#9;&#9;По умолчанию: max(m, n) * машинная_точность * max(сингулярное_число)<br>
&#9;&#9;<br>
&#9;Returns:<br>
&#9;&#9;Матрица размера (m, k) где k = m - rank(A) - размерность левого нуль-пространства.<br>
&#9;&#9;Столбцы образуют ортонормированный базис левого нуль-пространства.<br>
&#9;&#9;Если rank(A) = m, возвращает массив формы (m, 0).<br>
&#9;<br>
&#9;Notes:<br>
&#9;&#9;- Использует SVD-разложение для численной устойчивости<br>
&#9;&#9;- Размерность левого нуль-пространства = m - rank(A)<br>
&#9;&#9;- Векторы базиса ортонормированы: basis.T @ basis = I<br>
&#9;&#9;- Для получения проектора: P = basis @ basis.T<br>
&#9;&#9;- Работает в пространстве значений R^m<br>
&#9;&#9;- Эквивалент nullspace_basis(A.T)<br>
&#9;<br>
&#9;Examples:<br>
&#9;&#9;&gt;&gt;&gt; A = np.array([[1, 2], [2, 4], [3, 6]])  # Ранг 1<br>
&#9;&#9;&gt;&gt;&gt; L = left_nullspace_basis(A)<br>
&#9;&#9;&gt;&gt;&gt; L.shape  # (3, 2) - базис из 2 векторов<br>
&#9;&#9;&gt;&gt;&gt; np.allclose(A.T @ L, 0)  # Проверка: A^T @ y = 0<br>
&#9;&#9;True<br>
&#9;&quot;&quot;&quot;<br>
&#9;A = _ensure_inexact(A)<br>
&#9;u, s, vh = numpy.linalg.svd(A, full_matrices=True)<br>
&#9;<br>
&#9;# Определяем порог для малых сингулярных чисел<br>
&#9;if rtol is None:<br>
&#9;&#9;rtol = max(A.shape) * numpy.finfo(A.dtype).eps<br>
&#9;<br>
&#9;tol = rtol * s[0] if s.size &gt; 0 else rtol<br>
&#9;<br>
&#9;# Ранг матрицы = количество сингулярных чисел больше порога<br>
&#9;rank = numpy.sum(s &gt; tol)<br>
&#9;<br>
&#9;# Левое нуль-пространство = левые сингулярные векторы соответствующие нулевым σ<br>
&#9;left_null_basis = u[:, rank:]<br>
&#9;<br>
&#9;return left_null_basis<br>
<br>
<br>
def vector_projector(u):<br>
&#9;&quot;&quot;&quot;Возвращает матрицу ортогонального проектора на направление вектора u.<br>
&#9;<br>
&#9;Проектор P проецирует любой вектор v на направление u:<br>
&#9;&#9;P @ v = proj_u(v) = (u · v / u · u) * u<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;u: Вектор-направление размера (n,) или (n, 1)<br>
&#9;&#9;<br>
&#9;Returns:<br>
&#9;&#9;Матрица проектора размера (n, n)<br>
&#9;&#9;<br>
&#9;Raises:<br>
&#9;&#9;ValueError: Если u - нулевой вектор<br>
&#9;&#9;<br>
&#9;Notes:<br>
&#9;&#9;Проектор имеет вид: P = (u @ u.T) / (u.T @ u)<br>
&#9;&#9;Свойства:<br>
&#9;&#9;- P @ P = P (идемпотентность)<br>
&#9;&#9;- P.T = P (симметричность для вещественных векторов)<br>
&#9;&#9;- rank(P) = 1<br>
&#9;&#9;- trace(P) = 1<br>
&#9;<br>
&#9;Examples:<br>
&#9;&#9;&gt;&gt;&gt; u = np.array([1., 0., 0.])  # Вектор вдоль оси X<br>
&#9;&#9;&gt;&gt;&gt; P = vector_projector(u)<br>
&#9;&#9;&gt;&gt;&gt; v = np.array([3., 4., 5.])<br>
&#9;&#9;&gt;&gt;&gt; P @ v  # array([3., 0., 0.]) - проекция на ось X<br>
&#9;&quot;&quot;&quot;<br>
&#9;u = numpy.asarray(u)<br>
&#9;<br>
&#9;# Приводим к вектору-столбцу<br>
&#9;if u.ndim == 1:<br>
&#9;&#9;u = u.reshape(-1, 1)<br>
&#9;elif u.ndim == 2 and u.shape[1] != 1:<br>
&#9;&#9;raise ValueError(f&quot;u должен быть вектором, получена матрица формы {u.shape}&quot;)<br>
&#9;<br>
&#9;# Проверка на нулевой вектор<br>
&#9;norm_sq = numpy.vdot(u, u).real  # u^H @ u для комплексных векторов<br>
&#9;if norm_sq == 0:<br>
&#9;&#9;raise ValueError(&quot;Нельзя проецировать на нулевой вектор&quot;)<br>
&#9;<br>
&#9;# P = u @ u^H / (u^H @ u)<br>
&#9;return (u @ u.T.conj()) / norm_sq<br>
<br>
<br>
def subspace_projector(*vectors):<br>
&#9;&quot;&quot;&quot;Возвращает матрицу ортогонального проектора на подпространство, натянутое на векторы.<br>
&#9;<br>
&#9;Проектор P проецирует любой вектор v на подпространство span(u1, u2, ..., uk):<br>
&#9;&#9;P @ v = проекция v на span(vectors)<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;*vectors: Набор векторов, задающих подпространство.<br>
&#9;&#9;&#9;&#9;Каждый вектор размера (n,) или (n, 1).<br>
&#9;&#9;&#9;&#9;Векторы могут быть линейно зависимы (автоматически учитывается).<br>
&#9;&#9;<br>
&#9;Returns:<br>
&#9;&#9;Матрица проектора размера (n, n)<br>
&#9;&#9;<br>
&#9;Raises:<br>
&#9;&#9;ValueError: Если все векторы нулевые или не переданы<br>
&#9;&#9;<br>
&#9;Notes:<br>
&#9;&#9;- Автоматически ортогонализует векторы через SVD<br>
&#9;&#9;- Ранг проектора = rank(span(vectors))<br>
&#9;&#9;- Работает для любого количества векторов (k-векторы, бивекторы и т.д.)<br>
&#9;&#9;- Для 1 вектора эквивалентно vector_projector()<br>
&#9;&#9;- Для 2 векторов - проектор на плоскость (бивектор)<br>
&#9;&#9;<br>
&#9;Examples:<br>
&#9;&#9;&gt;&gt;&gt; # Проектор на плоскость XY<br>
&#9;&#9;&gt;&gt;&gt; u1 = np.array([1., 0., 0.])<br>
&#9;&#9;&gt;&gt;&gt; u2 = np.array([0., 1., 0.])<br>
&#9;&#9;&gt;&gt;&gt; P = subspace_projector(u1, u2)<br>
&#9;&#9;&gt;&gt;&gt; v = np.array([3., 4., 5.])<br>
&#9;&#9;&gt;&gt;&gt; P @ v  # array([3., 4., 0.]) - проекция на XY<br>
&#9;&quot;&quot;&quot;<br>
&#9;if len(vectors) == 0:<br>
&#9;&#9;raise ValueError(&quot;Необходимо передать хотя бы один вектор&quot;)<br>
&#9;<br>
&#9;# Собираем векторы в матрицу (каждый вектор - строка)<br>
&#9;vectors_array = [numpy.asarray(v).flatten() for v in vectors]<br>
&#9;A = numpy.vstack(vectors_array)<br>
&#9;<br>
&#9;# Используем rowspace_projector - он уже делает всё нужное:<br>
&#9;# - SVD разложение<br>
&#9;# - Учёт линейной зависимости<br>
&#9;# - Ортогонализацию<br>
&#9;return rowspace_projector(A)<br>
<br>
<br>
def orthogonal_complement(P):<br>
&#9;&quot;&quot;&quot;Возвращает проектор на ортогональное дополнение подпространства.<br>
&#9;<br>
&#9;Если P - проектор на подпространство V, то (I - P) - проектор на V⊥.<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;P: Матрица ортогонального проектора размера (n, n)<br>
&#9;&#9;<br>
&#9;Returns:<br>
&#9;&#9;Матрица проектора на ортогональное дополнение размера (n, n)<br>
&#9;&#9;<br>
&#9;Notes:<br>
&#9;&#9;- P + orthogonal_complement(P) = I<br>
&#9;&#9;- Работает для любого ортогонального проектора<br>
&#9;&#9;- dim(V) + dim(V⊥) = n<br>
&#9;&#9;<br>
&#9;Examples:<br>
&#9;&#9;&gt;&gt;&gt; # Проектор на ось X<br>
&#9;&#9;&gt;&gt;&gt; P_x = subspace_projector([1., 0., 0.])<br>
&#9;&#9;&gt;&gt;&gt; P_perp = orthogonal_complement(P_x)<br>
&#9;&#9;&gt;&gt;&gt; # P_perp проецирует на плоскость YZ<br>
&#9;&quot;&quot;&quot;<br>
&#9;P = numpy.asarray(P)<br>
&#9;n = P.shape[0]<br>
&#9;return numpy.eye(n, dtype=P.dtype) - P<br>
<br>
<br>
def is_in_subspace(v, P, tol=None):<br>
&#9;&quot;&quot;&quot;Проверяет, принадлежит ли вектор подпространству.<br>
&#9;<br>
&#9;Вектор v ∈ V &lt;=&gt; P @ v = v (проекция совпадает с исходным вектором).<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;v: Вектор размера (n,) или (n, 1)<br>
&#9;&#9;P: Проектор на подпространство V, размер (n, n)<br>
&#9;&#9;tol: Порог для сравнения ||P @ v - v||. <br>
&#9;&#9;&#9;По умолчанию: sqrt(n) * машинная_точность * ||v||<br>
&#9;&#9;<br>
&#9;Returns:<br>
&#9;&#9;True если v ∈ V, False иначе<br>
&#9;&#9;<br>
&#9;Notes:<br>
&#9;&#9;- Численно устойчиво для малых возмущений<br>
&#9;&#9;- Для нулевого вектора всегда возвращает True<br>
&#9;&#9;<br>
&#9;Examples:<br>
&#9;&#9;&gt;&gt;&gt; P_xy = subspace_projector([1,0,0], [0,1,0])<br>
&#9;&#9;&gt;&gt;&gt; is_in_subspace([3, 4, 0], P_xy)  # True<br>
&#9;&#9;&gt;&gt;&gt; is_in_subspace([3, 4, 5], P_xy)  # False<br>
&#9;&quot;&quot;&quot;<br>
&#9;v = numpy.asarray(v).flatten()<br>
&#9;P = numpy.asarray(P)<br>
&#9;<br>
&#9;# Проецируем вектор<br>
&#9;projected = P @ v<br>
&#9;<br>
&#9;# Вычисляем разность<br>
&#9;diff = projected - v<br>
&#9;diff_norm = numpy.linalg.norm(diff)<br>
&#9;<br>
&#9;# Порог по умолчанию<br>
&#9;if tol is None:<br>
&#9;&#9;v_norm = numpy.linalg.norm(v)<br>
&#9;&#9;if v_norm == 0:<br>
&#9;&#9;&#9;return True  # Нулевой вектор всегда в подпространстве<br>
&#9;&#9;tol = numpy.sqrt(len(v)) * numpy.finfo(P.dtype).eps * v_norm<br>
&#9;<br>
&#9;return diff_norm &lt;= tol<br>
<br>
<br>
def subspace_dimension(P, tol=None):<br>
&#9;&quot;&quot;&quot;Возвращает размерность подпространства, заданного проектором.<br>
&#9;<br>
&#9;Размерность = ранг проектора = след проектора.<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;P: Проектор на подпространство, размер (n, n)<br>
&#9;&#9;tol: Порог для определения ненулевых сингулярных чисел.<br>
&#9;&#9;&#9;По умолчанию: n * машинная_точность * max(сингулярное_число)<br>
&#9;&#9;<br>
&#9;Returns:<br>
&#9;&#9;Целое число - размерность подпространства (0 ≤ dim ≤ n)<br>
&#9;&#9;<br>
&#9;Notes:<br>
&#9;&#9;- Для ортогонального проектора: dim = rank(P) = trace(P)<br>
&#9;&#9;- Численно более устойчиво использовать ранг, а не след<br>
&#9;&#9;<br>
&#9;Examples:<br>
&#9;&#9;&gt;&gt;&gt; P_xy = subspace_projector([1,0,0], [0,1,0])<br>
&#9;&#9;&gt;&gt;&gt; subspace_dimension(P_xy)  # 2<br>
&#9;&#9;&gt;&gt;&gt; P_x = vector_projector([1,0,0])<br>
&#9;&#9;&gt;&gt;&gt; subspace_dimension(P_x)  # 1<br>
&#9;&quot;&quot;&quot;<br>
&#9;P = numpy.asarray(P)<br>
&#9;<br>
&#9;# Вычисляем ранг через SVD<br>
&#9;s = numpy.linalg.svd(P, compute_uv=False)<br>
&#9;<br>
&#9;if tol is None:<br>
&#9;&#9;tol = max(P.shape) * numpy.finfo(P.dtype).eps * s[0] if s.size &gt; 0 else 0<br>
&#9;<br>
&#9;rank = numpy.sum(s &gt; tol)<br>
&#9;<br>
&#9;return int(rank)<br>
<br>
<br>
def gram_schmidt(*vectors, tol=None):<br>
&#9;&quot;&quot;&quot;Ортогонализует набор векторов классическим методом Грама-Шмидта.<br>
&#9;<br>
&#9;Итеративно строит ортогональный базис: каждый следующий вектор ортогонализуется<br>
&#9;относительно всех предыдущих путём вычитания проекций.<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;*vectors: Набор векторов для ортогонализации.<br>
&#9;&#9;&#9;&#9;Каждый вектор размера (n,) или (n, 1).<br>
&#9;&#9;tol: Порог для определения нулевых векторов (линейная зависимость).<br>
&#9;&#9;&#9;По умолчанию: машинная_точность * 10<br>
&#9;&#9;<br>
&#9;Returns:<br>
&#9;&#9;Массив формы (n, k), где k ≤ len(vectors) - количество линейно независимых векторов.<br>
&#9;&#9;Столбцы образуют ортонормированный базис span(vectors).<br>
&#9;&#9;Если все векторы линейно зависимы, возвращает массив формы (n, 0).<br>
&#9;&#9;<br>
&#9;Notes:<br>
&#9;&#9;- Классический алгоритм Грама-Шмидта (не модифицированный)<br>
&#9;&#9;- Численно менее стабилен чем SVD, особенно для почти коллинеарных векторов<br>
&#9;&#9;- Порядок векторов критичен: первые векторы определяют базис<br>
&#9;&#9;- Для комплексных векторов использует эрмитово скалярное произведение<br>
&#9;&#9;<br>
&#9;Algorithm:<br>
&#9;&#9;u₁ = v₁ / ||v₁||<br>
&#9;&#9;u₂ = (v₂ - ⟨v₂, u₁⟩u₁) / ||v₂ - ⟨v₂, u₁⟩u₁||<br>
&#9;&#9;u₃ = (v₃ - ⟨v₃, u₁⟩u₁ - ⟨v₃, u₂⟩u₂) / ||...||<br>
&#9;&#9;...<br>
&#9;&#9;<br>
&#9;Examples:<br>
&#9;&#9;&gt;&gt;&gt; v1 = np.array([1., 1., 0.])<br>
&#9;&#9;&gt;&gt;&gt; v2 = np.array([1., 0., 0.])<br>
&#9;&#9;&gt;&gt;&gt; Q = gram_schmidt(v1, v2)<br>
&#9;&#9;&gt;&gt;&gt; np.allclose(Q.T @ Q, np.eye(2))  # Ортонормированность<br>
&#9;&#9;True<br>
&#9;&quot;&quot;&quot;<br>
&#9;if len(vectors) == 0:<br>
&#9;&#9;raise ValueError(&quot;Необходимо передать хотя бы один вектор&quot;)<br>
&#9;<br>
&#9;# Порог по умолчанию<br>
&#9;if tol is None:<br>
&#9;&#9;tol = 10 * numpy.finfo(float).eps<br>
&#9;<br>
&#9;# Преобразуем векторы в массивы-столбцы<br>
&#9;vectors_list = []<br>
&#9;n = None<br>
&#9;for v in vectors:<br>
&#9;&#9;v_arr = numpy.asarray(v).flatten()<br>
&#9;&#9;if n is None:<br>
&#9;&#9;&#9;n = len(v_arr)<br>
&#9;&#9;elif len(v_arr) != n:<br>
&#9;&#9;&#9;raise ValueError(f&quot;Все векторы должны иметь одинаковую размерность, получены {n} и {len(v_arr)}&quot;)<br>
&#9;&#9;vectors_list.append(v_arr)<br>
&#9;<br>
&#9;# Ортогонализация<br>
&#9;orthonormal_basis = []<br>
&#9;<br>
&#9;for v in vectors_list:<br>
&#9;&#9;# Начинаем с исходного вектора<br>
&#9;&#9;u = v.copy()<br>
&#9;&#9;<br>
&#9;&#9;# Вычитаем проекции на все предыдущие ортонормированные векторы<br>
&#9;&#9;for q in orthonormal_basis:<br>
&#9;&#9;&#9;# Проекция: proj_q(u) = ⟨u, q⟩ q<br>
&#9;&#9;&#9;# Для комплексных: используем vdot (сопряжённое скалярное произведение)<br>
&#9;&#9;&#9;projection_coef = numpy.vdot(q, u)<br>
&#9;&#9;&#9;u = u - projection_coef * q<br>
&#9;&#9;<br>
&#9;&#9;# Нормализуем<br>
&#9;&#9;norm = numpy.linalg.norm(u)<br>
&#9;&#9;<br>
&#9;&#9;# Если вектор стал нулевым (линейно зависим от предыдущих), пропускаем<br>
&#9;&#9;if norm &gt; tol:<br>
&#9;&#9;&#9;u_normalized = u / norm<br>
&#9;&#9;&#9;orthonormal_basis.append(u_normalized)<br>
&#9;<br>
&#9;# Если нет независимых векторов<br>
&#9;if len(orthonormal_basis) == 0:<br>
&#9;&#9;return numpy.empty((n, 0), dtype=vectors_list[0].dtype)<br>
&#9;<br>
&#9;# Собираем в матрицу (векторы = столбцы)<br>
&#9;Q = numpy.column_stack(orthonormal_basis)<br>
&#9;<br>
&#9;return Q<br>
<br>
<br>
def orthogonalize_svd(*vectors, tol=None):<br>
&#9;&quot;&quot;&quot;Ортогонализует набор векторов через SVD разложение.<br>
&#9;<br>
&#9;Строит ортонормированный базис подпространства, натянутого на входные векторы,<br>
&#9;используя сингулярное разложение (SVD). Численно более стабильный метод,<br>
&#9;чем классический Грам-Шмидт.<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;*vectors: Набор векторов для ортогонализации.<br>
&#9;&#9;&#9;&#9;Каждый вектор размера (n,) или (n, 1).<br>
&#9;&#9;tol: Относительный порог для определения линейной зависимости.<br>
&#9;&#9;&#9;По умолчанию: max(размеры) * машинная_точность<br>
&#9;&#9;<br>
&#9;Returns:<br>
&#9;&#9;Массив формы (n, k), где k ≤ len(vectors) - количество линейно независимых векторов.<br>
&#9;&#9;Столбцы образуют ортонормированный базис span(vectors).<br>
&#9;&#9;Если все векторы нулевые или линейно зависимые от нуля, возвращает массив формы (n, 0).<br>
&#9;&#9;<br>
&#9;Notes:<br>
&#9;&#9;- Использует SVD для численной устойчивости<br>
&#9;&#9;- Порядок векторов НЕ влияет на базис (в отличие от Грама-Шмидта)<br>
&#9;&#9;- SVD выбирает &quot;наилучший&quot; базис (главные направления)<br>
&#9;&#9;- Векторы базиса ортонормированы: Q.T @ Q = I<br>
&#9;&#9;- Для получения проектора: P = Q @ Q.T<br>
&#9;&#9;- Более медленный, но более точный чем Грам-Шмидт<br>
&#9;&#9;<br>
&#9;Examples:<br>
&#9;&#9;&gt;&gt;&gt; v1 = np.array([3., 4., 0.])<br>
&#9;&#9;&gt;&gt;&gt; v2 = np.array([1., 0., 1.])<br>
&#9;&#9;&gt;&gt;&gt; Q = orthogonalize_svd(v1, v2)<br>
&#9;&#9;&gt;&gt;&gt; Q.shape  # (3, 2)<br>
&#9;&#9;&gt;&gt;&gt; np.allclose(Q.T @ Q, np.eye(2))  # Ортонормированность<br>
&#9;&#9;True<br>
&#9;&#9;<br>
&#9;&#9;&gt;&gt;&gt; # Линейно зависимые векторы<br>
&#9;&#9;&gt;&gt;&gt; v1 = np.array([1., 0., 0.])<br>
&#9;&#9;&gt;&gt;&gt; v2 = np.array([2., 0., 0.])  # v2 = 2*v1<br>
&#9;&#9;&gt;&gt;&gt; Q = orthogonalize_svd(v1, v2)<br>
&#9;&#9;&gt;&gt;&gt; Q.shape  # (3, 1) - только один независимый вектор<br>
&#9;&quot;&quot;&quot;<br>
&#9;if len(vectors) == 0:<br>
&#9;&#9;raise ValueError(&quot;Необходимо передать хотя бы один вектор&quot;)<br>
&#9;<br>
&#9;# Преобразуем векторы в массив (векторы = строки)<br>
&#9;vectors_array = [numpy.asarray(v).flatten() for v in vectors]<br>
&#9;A = numpy.vstack(vectors_array)<br>
&#9;<br>
&#9;# SVD разложение<br>
&#9;u, s, vh = numpy.linalg.svd(A, full_matrices=True)<br>
&#9;<br>
&#9;# Определяем порог для линейной независимости<br>
&#9;if tol is None:<br>
&#9;&#9;tol = max(A.shape) * numpy.finfo(A.dtype).eps<br>
&#9;<br>
&#9;threshold = tol * s[0] if s.size &gt; 0 else tol<br>
&#9;<br>
&#9;# Ранг = количество значимых сингулярных чисел<br>
&#9;rank = numpy.sum(s &gt; threshold)<br>
&#9;<br>
&#9;# Ортонормированный базис = правые сингулярные векторы для ненулевых σ<br>
&#9;# Транспонируем, чтобы векторы были столбцами<br>
&#9;orthonormal_basis = vh[:rank].T.conj()<br>
&#9;<br>
&#9;return orthonormal_basis<br>
<br>
<br>
def orthogonalize(*vectors, method='svd', tol=None):<br>
&#9;&quot;&quot;&quot;Ортогонализует набор векторов одним из двух методов.<br>
&#9;<br>
&#9;Универсальная функция ортогонализации с выбором метода.<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;*vectors: Набор векторов для ортогонализации.<br>
&#9;&#9;&#9;&#9;Каждый вектор размера (n,) или (n, 1).<br>
&#9;&#9;method: Метод ортогонализации:<br>
&#9;&#9;&#9;&#9;- 'svd': SVD разложение (по умолчанию, более стабильный)<br>
&#9;&#9;&#9;&#9;- 'gram_schmidt' или 'gs': классический Грам-Шмидт<br>
&#9;&#9;tol: Порог для определения линейной зависимости.<br>
&#9;&#9;&#9;Интерпретация зависит от метода.<br>
&#9;&#9;<br>
&#9;Returns:<br>
&#9;&#9;Массив формы (n, k), где k ≤ len(vectors).<br>
&#9;&#9;Столбцы образуют ортонормированный базис span(vectors).<br>
&#9;&#9;<br>
&#9;Notes:<br>
&#9;&#9;- SVD: численно стабильный, базис не зависит от порядка векторов<br>
&#9;&#9;- Грам-Шмидт: быстрее, но менее стабильный, порядок векторов важен<br>
&#9;&#9;<br>
&#9;Examples:<br>
&#9;&#9;&gt;&gt;&gt; v1 = np.array([1., 1., 0.])<br>
&#9;&#9;&gt;&gt;&gt; v2 = np.array([1., 0., 0.])<br>
&#9;&#9;&gt;&gt;&gt; Q_svd = orthogonalize(v1, v2, method='svd')<br>
&#9;&#9;&gt;&gt;&gt; Q_gs = orthogonalize(v1, v2, method='gram_schmidt')<br>
&#9;&#9;&gt;&gt;&gt; # Оба ортонормированы, но могут давать разные базисы<br>
&#9;&quot;&quot;&quot;<br>
&#9;if method in ('svd', 'SVD'):<br>
&#9;&#9;return orthogonalize_svd(*vectors, tol=tol)<br>
&#9;elif method in ('gram_schmidt', 'gs', 'GS', 'Gram-Schmidt'):<br>
&#9;&#9;return gram_schmidt(*vectors, tol=tol)<br>
&#9;else:<br>
&#9;&#9;raise ValueError(f&quot;Неизвестный метод: {method}. Используйте 'svd' или 'gram_schmidt'&quot;)<br>
<br>
<br>
def is_projector(P, tol=None):<br>
&#9;&quot;&quot;&quot;Проверяет, является ли матрица ортогональным проектором.<br>
&#9;<br>
&#9;Ортогональный проектор должен удовлетворять двум условиям:<br>
&#9;1. Идемпотентность: P @ P = P<br>
&#9;2. Эрмитовость: P^H = P (для вещественных матриц: P.T = P)<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;P: Матрица для проверки, размер (n, n)<br>
&#9;&#9;tol: Порог для численного сравнения.<br>
&#9;&#9;&#9;По умолчанию: sqrt(n) * машинная_точность * ||P||<br>
&#9;&#9;<br>
&#9;Returns:<br>
&#9;&#9;True если P - ортогональный проектор, False иначе<br>
&#9;&#9;<br>
&#9;Notes:<br>
&#9;&#9;- Проверяет обе необходимые характеристики проектора<br>
&#9;&#9;- Учитывает численные погрешности через параметр tol<br>
&#9;&#9;- Для нулевой матрицы возвращает True (проектор на {0})<br>
&#9;&#9;- Дополнительно проверяется, что сингулярные числа ≈ 0 или 1<br>
&#9;&#9;<br>
&#9;Examples:<br>
&#9;&#9;&gt;&gt;&gt; # Проектор на ось X<br>
&#9;&#9;&gt;&gt;&gt; P = vector_projector([1., 0., 0.])<br>
&#9;&#9;&gt;&gt;&gt; is_projector(P)<br>
&#9;&#9;True<br>
&#9;&#9;<br>
&#9;&#9;&gt;&gt;&gt; # Обычная матрица (не проектор)<br>
&#9;&#9;&gt;&gt;&gt; A = np.array([[1, 2], [3, 4]])<br>
&#9;&#9;&gt;&gt;&gt; is_projector(A)<br>
&#9;&#9;False<br>
&#9;&#9;<br>
&#9;&#9;&gt;&gt;&gt; # Проектор на плоскость<br>
&#9;&#9;&gt;&gt;&gt; P = subspace_projector([1,0,0], [0,1,0])<br>
&#9;&#9;&gt;&gt;&gt; is_projector(P)<br>
&#9;&#9;True<br>
&#9;&quot;&quot;&quot;<br>
&#9;P = numpy.asarray(P)<br>
&#9;<br>
&#9;# Проверка квадратности<br>
&#9;if P.ndim != 2 or P.shape[0] != P.shape[1]:<br>
&#9;&#9;return False<br>
&#9;<br>
&#9;n = P.shape[0]<br>
&#9;<br>
&#9;# Конвертируем в float для корректной работы с numpy.finfo<br>
&#9;P = _ensure_inexact(P)<br>
&#9;<br>
&#9;# Определяем порог<br>
&#9;if tol is None:<br>
&#9;&#9;P_norm = numpy.linalg.norm(P)<br>
&#9;&#9;if P_norm == 0:<br>
&#9;&#9;&#9;return True  # Нулевая матрица - проектор на {0}<br>
&#9;&#9;tol = numpy.sqrt(n) * numpy.finfo(P.dtype).eps * P_norm<br>
&#9;<br>
&#9;# 1. Проверка идемпотентности: P @ P = P<br>
&#9;P_squared = P @ P<br>
&#9;idempotent = numpy.allclose(P_squared, P, atol=tol)<br>
&#9;<br>
&#9;if not idempotent:<br>
&#9;&#9;return False<br>
&#9;<br>
&#9;# 2. Проверка эрмитовости: P^H = P<br>
&#9;P_hermitian = P.T.conj()<br>
&#9;hermitian = numpy.allclose(P_hermitian, P, atol=tol)<br>
&#9;<br>
&#9;if not hermitian:<br>
&#9;&#9;return False<br>
&#9;<br>
&#9;# 3. Дополнительная проверка: сингулярные числа должны быть 0 или 1<br>
&#9;s = numpy.linalg.svd(P, compute_uv=False)<br>
&#9;<br>
&#9;# Более мягкий tolerance для сингулярных чисел<br>
&#9;# (SVD может давать разную точность на разных версиях NumPy/Python)<br>
&#9;svd_tol = max(tol, 10 * numpy.finfo(P.dtype).eps * P_norm)<br>
&#9;<br>
&#9;# Проверяем, что каждое сингулярное число близко либо к 0, либо к 1<br>
&#9;for sigma in s:<br>
&#9;&#9;# Расстояние до ближайшего из {0, 1}<br>
&#9;&#9;distance_to_binary = min(abs(sigma - 0.0), abs(sigma - 1.0))<br>
&#9;&#9;if distance_to_binary &gt; svd_tol:<br>
&#9;&#9;&#9;return False<br>
&#9;<br>
&#9;return True<br>
<br>
<br>
def projector_basis(P, rtol=None):<br>
&#9;&quot;&quot;&quot;Извлекает ортонормированный базис подпространства из проектора.<br>
&#9;<br>
&#9;Для проектора P на подпространство V возвращает матрицу Q, столбцы которой<br>
&#9;образуют ортонормированный базис V. Обратная операция: P = Q @ Q.T<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;P: Ортогональный проектор на подпространство, размер (n, n)<br>
&#9;&#9;rtol: Относительный порог для определения ранга проектора.<br>
&#9;&#9;&#9;По умолчанию: max(n) * машинная_точность<br>
&#9;&#9;<br>
&#9;Returns:<br>
&#9;&#9;Матрица размера (n, k) где k = dim(V) = rank(P).<br>
&#9;&#9;Столбцы образуют ортонормированный базис подпространства.<br>
&#9;&#9;Если P = 0 (тривиальное подпространство), возвращает массив формы (n, 0).<br>
&#9;&#9;<br>
&#9;Notes:<br>
&#9;&#9;- Использует SVD разложение проектора<br>
&#9;&#9;- Базис извлекается из правых сингулярных векторов<br>
&#9;&#9;- Векторы ортонормированы: Q.T @ Q = I_k<br>
&#9;&#9;- Проверка: P ≈ Q @ Q.T (с точностью до численных ошибок)<br>
&#9;&#9;<br>
&#9;Examples:<br>
&#9;&#9;&gt;&gt;&gt; # Создаём проектор на плоскость XY<br>
&#9;&#9;&gt;&gt;&gt; P = subspace_projector([1,0,0], [0,1,0])<br>
&#9;&#9;&gt;&gt;&gt; Q = projector_basis(P)<br>
&#9;&#9;&gt;&gt;&gt; Q.shape  # (3, 2)<br>
&#9;&#9;&gt;&gt;&gt; np.allclose(P, Q @ Q.T)  # Восстановление проектора<br>
&#9;&#9;True<br>
&#9;&quot;&quot;&quot;<br>
&#9;P = numpy.asarray(P)<br>
&#9;<br>
&#9;# SVD разложение проектора<br>
&#9;u, s, vh = numpy.linalg.svd(P, full_matrices=True)<br>
&#9;<br>
&#9;# Определяем порог<br>
&#9;if rtol is None:<br>
&#9;&#9;rtol = max(P.shape) * numpy.finfo(P.dtype).eps<br>
&#9;<br>
&#9;threshold = rtol * s[0] if s.size &gt; 0 else rtol<br>
&#9;<br>
&#9;# Ранг = количество значимых сингулярных чисел<br>
&#9;rank = numpy.sum(s &gt; threshold)<br>
&#9;<br>
&#9;if rank == 0:<br>
&#9;&#9;# Тривиальное подпространство {0}<br>
&#9;&#9;return numpy.empty((P.shape[0], 0), dtype=P.dtype)<br>
&#9;<br>
&#9;# Базис = правые сингулярные векторы для ненулевых σ<br>
&#9;# (транспонируем, чтобы векторы были столбцами)<br>
&#9;basis = vh[:rank].T.conj()<br>
&#9;<br>
&#9;return basis<br>
<br>
<br>
def subspace_intersection(P1, P2, tol=None):<br>
&#9;&quot;&quot;&quot;Возвращает проектор на пересечение двух подпространств.<br>
&#9;<br>
&#9;Вычисляет проектор на V1 ∩ V2, где V1 и V2 заданы проекторами P1 и P2.<br>
&#9;Использует метод через нуль-пространство: V1 ∩ V2 = V1 ∩ ker(I - P2).<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;P1: Проектор на первое подпространство V1, размер (n, n)<br>
&#9;&#9;P2: Проектор на второе подпространство V2, размер (n, n)<br>
&#9;&#9;tol: Порог для определения линейной зависимости.<br>
&#9;&#9;&#9;По умолчанию: max(n) * машинная_точность<br>
&#9;&#9;<br>
&#9;Returns:<br>
&#9;&#9;Матрица проектора на пересечение V1 ∩ V2, размер (n, n)<br>
&#9;&#9;<br>
&#9;Notes:<br>
&#9;&#9;- Если подпространства не пересекаются (только в 0), возвращает нулевой проектор<br>
&#9;&#9;- Метод: находим базис V1, проецируем на V2, ищем векторы, оставшиеся в V1<br>
&#9;&#9;- Математически: v ∈ V1 ∩ V2 ⟺ v ∈ V1 и P2 @ v = v<br>
&#9;&#9;- dim(V1 ∩ V2) ≤ min(dim(V1), dim(V2))<br>
&#9;&#9;- Для ортогональных подпространств: V1 ∩ V2 = {0}<br>
&#9;&#9;<br>
&#9;Examples:<br>
&#9;&#9;&gt;&gt;&gt; # Плоскость XY и плоскость XZ пересекаются по оси X<br>
&#9;&#9;&gt;&gt;&gt; P_xy = subspace_projector([1,0,0], [0,1,0])<br>
&#9;&#9;&gt;&gt;&gt; P_xz = subspace_projector([1,0,0], [0,0,1])<br>
&#9;&#9;&gt;&gt;&gt; P_x = subspace_intersection(P_xy, P_xz)<br>
&#9;&#9;&gt;&gt;&gt; # P_x - проектор на ось X (dim = 1)<br>
&#9;&#9;<br>
&#9;&#9;&gt;&gt;&gt; # Ортогональные подпространства<br>
&#9;&#9;&gt;&gt;&gt; P_x = vector_projector([1,0,0])<br>
&#9;&#9;&gt;&gt;&gt; P_y = vector_projector([0,1,0])<br>
&#9;&#9;&gt;&gt;&gt; P_int = subspace_intersection(P_x, P_y)<br>
&#9;&#9;&gt;&gt;&gt; # P_int ≈ 0 (пересечение пустое)<br>
&#9;&quot;&quot;&quot;<br>
&#9;P1 = numpy.asarray(P1)<br>
&#9;P2 = numpy.asarray(P2)<br>
&#9;<br>
&#9;if P1.shape != P2.shape:<br>
&#9;&#9;raise ValueError(f&quot;Проекторы должны иметь одинаковый размер, получены {P1.shape} и {P2.shape}&quot;)<br>
&#9;<br>
&#9;# Извлекаем базис V1 из проектора P1<br>
&#9;basis1 = projector_basis(P1, rtol=tol)<br>
&#9;<br>
&#9;if basis1.size == 0:<br>
&#9;&#9;# V1 = {0}, пересечение пустое<br>
&#9;&#9;return numpy.zeros_like(P1)<br>
&#9;<br>
&#9;# Проецируем базисные векторы V1 на V2<br>
&#9;# Вектор v ∈ V1 лежит в V1 ∩ V2 ⟺ P2 @ v = v<br>
&#9;projected_basis = P2 @ basis1<br>
&#9;<br>
&#9;# Разность: (P2 @ v - v) должна быть нулевой для векторов из пересечения<br>
&#9;diff = projected_basis - basis1<br>
&#9;<br>
&#9;# Находим нуль-пространство diff (линейные комбинации столбцов basis1,<br>
&#9;# которые не изменяются при проекции на V2)<br>
&#9;# diff @ c ≈ 0  =&gt;  c задаёт вектор из пересечения<br>
&#9;<br>
&#9;# Определяем абсолютный порог для сингулярных чисел<br>
&#9;# Используем норму базиса как характерный масштаб<br>
&#9;if tol is None:<br>
&#9;&#9;tol = max(P1.shape) * numpy.finfo(P1.dtype).eps<br>
&#9;<br>
&#9;# Абсолютный порог учитывает масштаб задачи<br>
&#9;threshold = tol * max(1.0, numpy.linalg.norm(basis1))<br>
&#9;<br>
&#9;# Используем существующую функцию с абсолютным порогом<br>
&#9;null_coefs = nullspace_basis(diff, atol=threshold)<br>
&#9;<br>
&#9;if null_coefs.size == 0:<br>
&#9;&#9;# Пересечение пустое (только нулевой вектор)<br>
&#9;&#9;return numpy.zeros_like(P1)<br>
&#9;<br>
&#9;# Строим базис пересечения: линейные комбинации basis1<br>
&#9;intersection_basis = basis1 @ null_coefs<br>
&#9;<br>
&#9;# Проектор = базис @ базис^H<br>
&#9;return intersection_basis @ intersection_basis.T.conj()<br>
<br>
<br>
def project_onto_affine(x, C, b):<br>
&#9;&quot;&quot;&quot;Возвращает ортогональную проекцию вектора x на аффинное множество, заданное C @ y = b.<br>
&#9;<br>
&#9;Args:<br>
&#9;&#9;x: Вектор размера (n,)<br>
&#9;&#9;C: Линейно-независимая матрица размера (m, n), задающая линейное отображение<br>
&#9;&#9;b: Вектор размера (m,), задающий сдвиг аффинного множества<br>
<br>
&#9;Returns:<br>
&#9;&#9;Вектор размера (n,) - проекция x на множество {y | C @ y = b}<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;x = numpy.asarray(x).flatten()<br>
&#9;C = numpy.asarray(C)<br>
&#9;b = numpy.asarray(b).flatten()<br>
&#9;<br>
&#9;if C.shape[0] != b.shape[0]:<br>
&#9;&#9;raise ValueError(f&quot;Размерность b должна соответствовать числу строк C, получены {C.shape[0]} и {b.shape[0]}&quot;)<br>
&#9;if C.shape[1] != x.shape[0]:<br>
&#9;&#9;raise ValueError(f&quot;Размерность x должна соответствовать числу столбцов C, получены {C.shape[1]} и {x.shape[0]}&quot;)<br>
&#9;<br>
&#9;Ct = C.T.conj()<br>
&#9;CCt_inv = numpy.linalg.pinv(C @ Ct)<br>
&#9;projection = x - Ct @ (CCt_inv @ (C @ x - b))<br>
&#9;return projection<br>
<br>
def affine_projector(C, b):<br>
&#9;&quot;&quot;&quot;Возвращает проектор на аффинное множество A, заданное C @ y = b и вектор смещения B:<br>
<br>
&#9;Решение следует подставлять в форму x^ = x - (A.x - B).<br>
&#9;Здесь<br>
&#9;A = C.T @ (C @ C.T)^(-1) @ C<br>
&#9;B = C.T @ (C @ C.T)^(-1) @ b<br>
&#9;&quot;&quot;&quot;<br>
&#9;C = numpy.asarray(C)<br>
&#9;b = numpy.asarray(b).flatten()<br>
&#9;<br>
&#9;if C.shape[0] != b.shape[0]:<br>
&#9;&#9;raise ValueError(f&quot;Размерность b должна соответствовать числу строк C, получены {C.shape[0]} и {b.shape[0]}&quot;)<br>
&#9;<br>
&#9;Ct = C.T.conj()<br>
&#9;CCt_inv = numpy.linalg.pinv(C @ Ct)<br>
&#9;<br>
&#9;K = Ct @ CCt_inv<br>
&#9;A = K @ C<br>
&#9;B = K @ b<br>
<br>
&#9;return A, B<br>
<br>
def metric_project_onto_constraints(<br>
&#9;&#9;q: numpy.ndarray, <br>
&#9;&#9;H: numpy.ndarray,<br>
&#9;&#9;M_inv: numpy.ndarray,<br>
&#9;&#9;error: numpy.ndarray = None,<br>
&#9;&#9;h: numpy.ndarray = None) -&gt; numpy.ndarray:<br>
&#9;&quot;&quot;&quot;Проецировать скорости на ограничения<br>
&#9;<br>
&#9;q - текущий вектор<br>
&#9;H - матрица ограничений<br>
&#9;M_inv - метрическая матрица<br>
&#9;<br>
&#9;Одно из двух должно быть задано:<br>
&#9;&#9;error - текущая ошибка<br>
&#9;&#9;h - правая часть ограничений<br>
&#9;&quot;&quot;&quot;<br>
&#9;if error is None:<br>
&#9;&#9;error = H @ q - h<br>
<br>
&#9;S = H @ M_inv @ H.T<br>
<br>
&#9;lmbda = numpy.linalg.solve(S, error)<br>
&#9;corrected = q - M_inv @ H.T @ lmbda<br>
<br>
&#9;return corrected <br>
<!-- END SCAT CODE -->
</body>
</html>
