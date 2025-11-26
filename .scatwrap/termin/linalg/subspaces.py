<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/linalg/subspaces.py</title>
</head>
<body>
<pre><code>
import numpy


def _ensure_inexact(A):
    &quot;&quot;&quot;Конвертирует целочисленные массивы в float, сохраняя float/complex типы.&quot;&quot;&quot;
    A = numpy.asarray(A)
    if not numpy.issubdtype(A.dtype, numpy.inexact):
        # Конвертируем целые числа в float64
        return numpy.asarray(A, dtype=float)
    # Оставляем float32/float64/complex как есть
    return A


def nullspace_projector(A):
    &quot;&quot;&quot;Возвращает матрицу ортогонального проектора на нуль-пространство матрицы A.
    
    Проектор P обладает свойствами:
    - A @ P = 0 (проекция попадает в нуль-пространство)
    - P @ P = P (идемпотентность)
    - P.T = P (для вещественных матриц - симметричность)
    
    Args:
        A: Матрица размера (m, n)
        
    Returns:
        Матрица проектора размера (n, n)
        
    Notes:
        Для проекции вектора v на нуль-пространство: v_proj = P @ v
        Использует SVD-разложение для оптимальной производительности.
    &quot;&quot;&quot;
    A = _ensure_inexact(A)
    u, s, vh = numpy.linalg.svd(A, full_matrices=True)
    
    # Определяем ранг матрицы
    tol = max(A.shape) * numpy.finfo(A.dtype).eps * s[0] if s.size &gt; 0 else 0
    rank = numpy.sum(s &gt; tol)
    
    # Базис нуль-пространства = правые сингулярные векторы для нулевых сингулярных чисел
    null_basis = vh[rank:].T.conj()
    
    # Проектор = базис @ базис.T
    if null_basis.size &gt; 0:
        return null_basis @ null_basis.T.conj()
    else:
        # Нуль-пространство пустое - возвращаем нулевой проектор
        return numpy.zeros((A.shape[1], A.shape[1]), dtype=A.dtype)


def nullspace_basis_svd(A, rtol=None, atol=None):
    &quot;&quot;&quot;Ортонормированный базис ker(A), полученный через SVD A = U Σ V^H.

    Правые сингулярные векторы, соответствующие нулевым σ, образуют базис
    нуль-пространства. В реализации отбрасываются σ ниже заданного порога.

    Args:
        A: Матрица размера (m, n)
        rtol: Относительный порог для сингулярных чисел (≈ eps · max(m, n)).
        atol: Абсолютный порог (если задан, имеет приоритет над rtol).

    Returns:
        Матрица (n, k) с ортонормированными столбцами basis, где A @ basis = 0.
        Если ker(A) тривиально, возвращается массив формы (n, 0).
    &quot;&quot;&quot;
    A = _ensure_inexact(A)
    u, s, vh = numpy.linalg.svd(A, full_matrices=True)

    if atol is not None:
        tol = atol
    else:
        if rtol is None:
            rtol = max(A.shape) * numpy.finfo(A.dtype).eps
        tol = rtol * s[0] if s.size &gt; 0 else rtol

    rank = numpy.sum(s &gt; tol)
    null_basis = vh[rank:].T.conj()

    if null_basis.size == 0:
        return numpy.zeros((A.shape[1], 0), dtype=A.dtype)

    return null_basis


def nullspace_basis_qr(A, rtol=None, atol=None):
    &quot;&quot;&quot;Ортонормированный базис ker(A) по формуле A^T = Q R (полный QR).

    Если r = rank(A), то строки A лежат в span(Q[:, :r]) и
    ker(A) = (rowspace(A))^⊥ = span(Q[:, r:]). Хвостовые столбцы Q уже
    ортонормированы и задают искомый базис.

    Args:
        A: Матрица размера (m, n)
        rtol: Относительный порог для диагонали R.
        atol: Абсолютный порог (если задан, имеет приоритет).

    Returns:
        Матрица (n, k) с ортонормированными столбцами ker(A).
        Если дополнение тривиально, возвращается массив формы (n, 0).
    &quot;&quot;&quot;
    A = _ensure_inexact(A)
    m, n = A.shape

    if n == 0:
        return numpy.zeros((0, 0), dtype=A.dtype)

    Q, R = numpy.linalg.qr(A.T, mode=&quot;complete&quot;)
    diag_len = min(n, m)

    if diag_len == 0:
        rank = 0
    else:
        diag = numpy.abs(numpy.diag(R[:diag_len, :diag_len]))
        max_diag = diag.max() if diag.size &gt; 0 else 0.0

        if atol is not None:
            tol = atol
        else:
            if rtol is None:
                rtol = max(m, n) * numpy.finfo(A.dtype).eps
            tol = rtol * max_diag if max_diag &gt; 0 else rtol

        rank = int(numpy.sum(diag &gt; tol))

    return Q[:, rank:]


def nullspace_basis(A, rtol=None, atol=None, method=&quot;svd&quot;):
    &quot;&quot;&quot;Возвращает ортонормированный базис ker(A) с выбранным алгоритмом.

    Args:
        A: Матрица размера (m, n)
        rtol: Относительный порог толеранса.
        atol: Абсолютный порог толеранса.
        method: 'svd' (устойчивее) или 'qr' (быстрее для узких матриц).

    Returns:
        Матрица (n, k), столбцы которой образуют базис нуль-пространства.

    Raises:
        ValueError: если указан неподдерживаемый method.
    &quot;&quot;&quot;
    if method is None:
        method = &quot;svd&quot;

    if method == &quot;svd&quot;:
        return nullspace_basis_svd(A, rtol=rtol, atol=atol)
    if method == &quot;qr&quot;:
        return nullspace_basis_qr(A, rtol=rtol, atol=atol)

    raise ValueError(f&quot;Unsupported nullspace method '{method}'. Use 'svd' or 'qr'.&quot;)


def rowspace_projector(A):
    &quot;&quot;&quot;Возвращает матрицу ортогонального проектора на пространство строк матрицы A.
    
    Пространство строк (row space) - это ортогональное дополнение к нуль-пространству.
    Проектор P обладает свойствами:
    - P @ v лежит в пространстве строк для любого v
    - P + nullspace_projector(A) = I (дополнение)
    - P @ P = P (идемпотентность)
    - P.T = P (для вещественных матриц - симметричность)
    
    Args:
        A: Матрица размера (m, n)
        
    Returns:
        Матрица проектора размера (n, n)
        
    Notes:
        Для проекции вектора v на пространство строк: v_proj = P @ v
        rowspace_projector(A) = I - nullspace_projector(A)
    &quot;&quot;&quot;
    A = _ensure_inexact(A)
    u, s, vh = numpy.linalg.svd(A, full_matrices=True)
    
    # Определяем ранг матрицы
    tol = max(A.shape) * numpy.finfo(A.dtype).eps * s[0] if s.size &gt; 0 else 0
    rank = numpy.sum(s &gt; tol)
    
    # Базис пространства строк = правые сингулярные векторы для ненулевых σ
    row_basis = vh[:rank].T.conj()
    
    # Проектор = базис @ базис.T
    if row_basis.size &gt; 0:
        return row_basis @ row_basis.T.conj()
    else:
        # Пространство строк пустое - возвращаем нулевой проектор
        return numpy.zeros((A.shape[1], A.shape[1]), dtype=A.dtype)


def rowspace_basis(A, rtol=None):
    &quot;&quot;&quot;Возвращает ортонормированный базис пространства строк матрицы A.
    
    Пространство строк (row space) состоит из всех линейных комбинаций строк A.
    Это ортогональное дополнение к нуль-пространству: rowspace ⊕ nullspace = R^n.
    
    Args:
        A: Матрица размера (m, n)
        rtol: Относительный порог для определения нулевых сингулярных чисел.
              По умолчанию: max(m, n) * машинная_точность * max(сингулярное_число)
        
    Returns:
        Матрица размера (n, k) где k = rank(A) - размерность пространства строк.
        Столбцы образуют ортонормированный базис пространства строк.
        Если rank(A) = 0, возвращает массив формы (n, 0).
    
    Notes:
        - Использует SVD-разложение для численной устойчивости
        - Размерность пространства строк = rank(A)
        - Векторы базиса ортонормированы: basis.T @ basis = I
        - Для получения проектора: P = basis @ basis.T
        - Дополнение: rowspace_basis ⊕ nullspace_basis = полный базис R^n
    
    Examples:
        &gt;&gt;&gt; A = np.array([[1, 2, 3], [2, 4, 6]])  # Ранг 1
        &gt;&gt;&gt; R = rowspace_basis(A)
        &gt;&gt;&gt; R.shape  # (3, 1) - базис из 1 вектора
        &gt;&gt;&gt; N = nullspace_basis(A)
        &gt;&gt;&gt; N.shape  # (3, 2) - дополнение
    &quot;&quot;&quot;
    A = _ensure_inexact(A)
    u, s, vh = numpy.linalg.svd(A, full_matrices=True)
    
    # Определяем порог для малых сингулярных чисел
    if rtol is None:
        rtol = max(A.shape) * numpy.finfo(A.dtype).eps
    
    tol = rtol * s[0] if s.size &gt; 0 else rtol
    
    # Ранг матрицы = количество сингулярных чисел больше порога
    rank = numpy.sum(s &gt; tol)
    
    # Пространство строк = правые сингулярные векторы соответствующие ненулевым σ
    # Берём строки vh с индексами [:rank] и транспонируем
    row_basis = vh[:rank].T.conj()
    
    return row_basis


def colspace_projector(A):
    &quot;&quot;&quot;Возвращает матрицу ортогонального проектора на пространство столбцов матрицы A.
    
    Пространство столбцов (column space, range) - это образ отображения A.
    Проектор P обладает свойствами:
    - P @ b лежит в colspace для любого b
    - P + left_nullspace_projector(A) = I (дополнение)
    - P @ P = P (идемпотентность)
    - P.T = P (для вещественных матриц - симметричность)
    
    Args:
        A: Матрица размера (m, n)
        
    Returns:
        Матрица проектора размера (m, m)
        
    Notes:
        Для проекции вектора b на пространство столбцов: b_proj = P @ b
        Если Ax = b несовместна, то Ax = P @ b всегда разрешима.
        Работает в пространстве значений R^m.
    &quot;&quot;&quot;
    A = _ensure_inexact(A)
    u, s, vh = numpy.linalg.svd(A, full_matrices=True)
    
    # Определяем ранг матрицы
    tol = max(A.shape) * numpy.finfo(A.dtype).eps * s[0] if s.size &gt; 0 else 0
    rank = numpy.sum(s &gt; tol)
    
    # Базис пространства столбцов = левые сингулярные векторы для ненулевых σ
    col_basis = u[:, :rank]
    
    # Проектор = базис @ базис.T
    if col_basis.size &gt; 0:
        return col_basis @ col_basis.T.conj()
    else:
        # Пространство столбцов пустое - возвращаем нулевой проектор
        return numpy.zeros((A.shape[0], A.shape[0]), dtype=A.dtype)


def colspace_basis(A, rtol=None):
    &quot;&quot;&quot;Возвращает ортонормированный базис пространства столбцов матрицы A.
    
    Пространство столбцов (column space, range, образ) состоит из всех векторов вида A @ x.
    Это ортогональное дополнение к левому нуль-пространству: colspace ⊕ left_nullspace = R^m.
    
    Args:
        A: Матрица размера (m, n)
        rtol: Относительный порог для определения нулевых сингулярных чисел.
              По умолчанию: max(m, n) * машинная_точность * max(сингулярное_число)
        
    Returns:
        Матрица размера (m, k) где k = rank(A) - размерность пространства столбцов.
        Столбцы образуют ортонормированный базис пространства столбцов.
        Если rank(A) = 0, возвращает массив формы (m, 0).
    
    Notes:
        - Использует SVD-разложение для численной устойчивости
        - Размерность пространства столбцов = rank(A)
        - Векторы базиса ортонормированы: basis.T @ basis = I
        - Для получения проектора: P = basis @ basis.T
        - Работает в пространстве значений R^m
        - Эквивалент scipy.linalg.orth(A)
    
    Examples:
        &gt;&gt;&gt; A = np.array([[1, 0], [2, 0], [3, 0]])  # Ранг 1
        &gt;&gt;&gt; C = colspace_basis(A)
        &gt;&gt;&gt; C.shape  # (3, 1) - базис из 1 вектора
        &gt;&gt;&gt; # Любой вектор A @ x лежит в span(C)
    &quot;&quot;&quot;
    A = _ensure_inexact(A)
    u, s, vh = numpy.linalg.svd(A, full_matrices=True)
    
    # Определяем порог для малых сингулярных чисел
    if rtol is None:
        rtol = max(A.shape) * numpy.finfo(A.dtype).eps
    
    tol = rtol * s[0] if s.size &gt; 0 else rtol
    
    # Ранг матрицы = количество сингулярных чисел больше порога
    rank = numpy.sum(s &gt; tol)
    
    # Пространство столбцов = левые сингулярные векторы соответствующие ненулевым σ
    col_basis = u[:, :rank]
    
    return col_basis


def left_nullspace_projector(A):
    &quot;&quot;&quot;Возвращает матрицу ортогонального проектора на левое нуль-пространство матрицы A.
    
    Левое нуль-пространство состоит из векторов y таких, что A^T @ y = 0.
    Это ортогональное дополнение к пространству столбцов.
    Проектор P обладает свойствами:
    - A^T @ P = 0 (эквивалентно: P @ A = 0)
    - P + colspace_projector(A) = I (дополнение)
    - P @ P = P (идемпотентность)
    - P.T = P (для вещественных матриц - симметричность)
    
    Args:
        A: Матрица размера (m, n)
        
    Returns:
        Матрица проектора размера (m, m)
        
    Notes:
        Для проекции вектора b на левое нуль-пространство: b_proj = P @ b
        left_nullspace(A) = nullspace(A^T)
        Работает в пространстве значений R^m.
    &quot;&quot;&quot;
    A = _ensure_inexact(A)
    u, s, vh = numpy.linalg.svd(A, full_matrices=True)
    
    # Определяем ранг матрицы
    tol = max(A.shape) * numpy.finfo(A.dtype).eps * s[0] if s.size &gt; 0 else 0
    rank = numpy.sum(s &gt; tol)
    
    # Базис левого нуль-пространства = левые сингулярные векторы для нулевых σ
    left_null_basis = u[:, rank:]
    
    # Проектор = базис @ базис.T
    if left_null_basis.size &gt; 0:
        return left_null_basis @ left_null_basis.T.conj()
    else:
        # Левое нуль-пространство пустое - возвращаем нулевой проектор
        return numpy.zeros((A.shape[0], A.shape[0]), dtype=A.dtype)


def left_nullspace_basis(A, rtol=None):
    &quot;&quot;&quot;Возвращает ортонормированный базис левого нуль-пространства матрицы A.
    
    Левое нуль-пространство состоит из векторов y таких, что A^T @ y = 0.
    Это ортогональное дополнение к пространству столбцов: left_nullspace ⊕ colspace = R^m.
    
    Args:
        A: Матрица размера (m, n)
        rtol: Относительный порог для определения нулевых сингулярных чисел.
              По умолчанию: max(m, n) * машинная_точность * max(сингулярное_число)
        
    Returns:
        Матрица размера (m, k) где k = m - rank(A) - размерность левого нуль-пространства.
        Столбцы образуют ортонормированный базис левого нуль-пространства.
        Если rank(A) = m, возвращает массив формы (m, 0).
    
    Notes:
        - Использует SVD-разложение для численной устойчивости
        - Размерность левого нуль-пространства = m - rank(A)
        - Векторы базиса ортонормированы: basis.T @ basis = I
        - Для получения проектора: P = basis @ basis.T
        - Работает в пространстве значений R^m
        - Эквивалент nullspace_basis(A.T)
    
    Examples:
        &gt;&gt;&gt; A = np.array([[1, 2], [2, 4], [3, 6]])  # Ранг 1
        &gt;&gt;&gt; L = left_nullspace_basis(A)
        &gt;&gt;&gt; L.shape  # (3, 2) - базис из 2 векторов
        &gt;&gt;&gt; np.allclose(A.T @ L, 0)  # Проверка: A^T @ y = 0
        True
    &quot;&quot;&quot;
    A = _ensure_inexact(A)
    u, s, vh = numpy.linalg.svd(A, full_matrices=True)
    
    # Определяем порог для малых сингулярных чисел
    if rtol is None:
        rtol = max(A.shape) * numpy.finfo(A.dtype).eps
    
    tol = rtol * s[0] if s.size &gt; 0 else rtol
    
    # Ранг матрицы = количество сингулярных чисел больше порога
    rank = numpy.sum(s &gt; tol)
    
    # Левое нуль-пространство = левые сингулярные векторы соответствующие нулевым σ
    left_null_basis = u[:, rank:]
    
    return left_null_basis


def vector_projector(u):
    &quot;&quot;&quot;Возвращает матрицу ортогонального проектора на направление вектора u.
    
    Проектор P проецирует любой вектор v на направление u:
        P @ v = proj_u(v) = (u · v / u · u) * u
    
    Args:
        u: Вектор-направление размера (n,) или (n, 1)
        
    Returns:
        Матрица проектора размера (n, n)
        
    Raises:
        ValueError: Если u - нулевой вектор
        
    Notes:
        Проектор имеет вид: P = (u @ u.T) / (u.T @ u)
        Свойства:
        - P @ P = P (идемпотентность)
        - P.T = P (симметричность для вещественных векторов)
        - rank(P) = 1
        - trace(P) = 1
    
    Examples:
        &gt;&gt;&gt; u = np.array([1., 0., 0.])  # Вектор вдоль оси X
        &gt;&gt;&gt; P = vector_projector(u)
        &gt;&gt;&gt; v = np.array([3., 4., 5.])
        &gt;&gt;&gt; P @ v  # array([3., 0., 0.]) - проекция на ось X
    &quot;&quot;&quot;
    u = numpy.asarray(u)
    
    # Приводим к вектору-столбцу
    if u.ndim == 1:
        u = u.reshape(-1, 1)
    elif u.ndim == 2 and u.shape[1] != 1:
        raise ValueError(f&quot;u должен быть вектором, получена матрица формы {u.shape}&quot;)
    
    # Проверка на нулевой вектор
    norm_sq = numpy.vdot(u, u).real  # u^H @ u для комплексных векторов
    if norm_sq == 0:
        raise ValueError(&quot;Нельзя проецировать на нулевой вектор&quot;)
    
    # P = u @ u^H / (u^H @ u)
    return (u @ u.T.conj()) / norm_sq


def subspace_projector(*vectors):
    &quot;&quot;&quot;Возвращает матрицу ортогонального проектора на подпространство, натянутое на векторы.
    
    Проектор P проецирует любой вектор v на подпространство span(u1, u2, ..., uk):
        P @ v = проекция v на span(vectors)
    
    Args:
        *vectors: Набор векторов, задающих подпространство.
                  Каждый вектор размера (n,) или (n, 1).
                  Векторы могут быть линейно зависимы (автоматически учитывается).
        
    Returns:
        Матрица проектора размера (n, n)
        
    Raises:
        ValueError: Если все векторы нулевые или не переданы
        
    Notes:
        - Автоматически ортогонализует векторы через SVD
        - Ранг проектора = rank(span(vectors))
        - Работает для любого количества векторов (k-векторы, бивекторы и т.д.)
        - Для 1 вектора эквивалентно vector_projector()
        - Для 2 векторов - проектор на плоскость (бивектор)
        
    Examples:
        &gt;&gt;&gt; # Проектор на плоскость XY
        &gt;&gt;&gt; u1 = np.array([1., 0., 0.])
        &gt;&gt;&gt; u2 = np.array([0., 1., 0.])
        &gt;&gt;&gt; P = subspace_projector(u1, u2)
        &gt;&gt;&gt; v = np.array([3., 4., 5.])
        &gt;&gt;&gt; P @ v  # array([3., 4., 0.]) - проекция на XY
    &quot;&quot;&quot;
    if len(vectors) == 0:
        raise ValueError(&quot;Необходимо передать хотя бы один вектор&quot;)
    
    # Собираем векторы в матрицу (каждый вектор - строка)
    vectors_array = [numpy.asarray(v).flatten() for v in vectors]
    A = numpy.vstack(vectors_array)
    
    # Используем rowspace_projector - он уже делает всё нужное:
    # - SVD разложение
    # - Учёт линейной зависимости
    # - Ортогонализацию
    return rowspace_projector(A)


def orthogonal_complement(P):
    &quot;&quot;&quot;Возвращает проектор на ортогональное дополнение подпространства.
    
    Если P - проектор на подпространство V, то (I - P) - проектор на V⊥.
    
    Args:
        P: Матрица ортогонального проектора размера (n, n)
        
    Returns:
        Матрица проектора на ортогональное дополнение размера (n, n)
        
    Notes:
        - P + orthogonal_complement(P) = I
        - Работает для любого ортогонального проектора
        - dim(V) + dim(V⊥) = n
        
    Examples:
        &gt;&gt;&gt; # Проектор на ось X
        &gt;&gt;&gt; P_x = subspace_projector([1., 0., 0.])
        &gt;&gt;&gt; P_perp = orthogonal_complement(P_x)
        &gt;&gt;&gt; # P_perp проецирует на плоскость YZ
    &quot;&quot;&quot;
    P = numpy.asarray(P)
    n = P.shape[0]
    return numpy.eye(n, dtype=P.dtype) - P


def is_in_subspace(v, P, tol=None):
    &quot;&quot;&quot;Проверяет, принадлежит ли вектор подпространству.
    
    Вектор v ∈ V &lt;=&gt; P @ v = v (проекция совпадает с исходным вектором).
    
    Args:
        v: Вектор размера (n,) или (n, 1)
        P: Проектор на подпространство V, размер (n, n)
        tol: Порог для сравнения ||P @ v - v||. 
             По умолчанию: sqrt(n) * машинная_точность * ||v||
        
    Returns:
        True если v ∈ V, False иначе
        
    Notes:
        - Численно устойчиво для малых возмущений
        - Для нулевого вектора всегда возвращает True
        
    Examples:
        &gt;&gt;&gt; P_xy = subspace_projector([1,0,0], [0,1,0])
        &gt;&gt;&gt; is_in_subspace([3, 4, 0], P_xy)  # True
        &gt;&gt;&gt; is_in_subspace([3, 4, 5], P_xy)  # False
    &quot;&quot;&quot;
    v = numpy.asarray(v).flatten()
    P = numpy.asarray(P)
    
    # Проецируем вектор
    projected = P @ v
    
    # Вычисляем разность
    diff = projected - v
    diff_norm = numpy.linalg.norm(diff)
    
    # Порог по умолчанию
    if tol is None:
        v_norm = numpy.linalg.norm(v)
        if v_norm == 0:
            return True  # Нулевой вектор всегда в подпространстве
        tol = numpy.sqrt(len(v)) * numpy.finfo(P.dtype).eps * v_norm
    
    return diff_norm &lt;= tol


def subspace_dimension(P, tol=None):
    &quot;&quot;&quot;Возвращает размерность подпространства, заданного проектором.
    
    Размерность = ранг проектора = след проектора.
    
    Args:
        P: Проектор на подпространство, размер (n, n)
        tol: Порог для определения ненулевых сингулярных чисел.
             По умолчанию: n * машинная_точность * max(сингулярное_число)
        
    Returns:
        Целое число - размерность подпространства (0 ≤ dim ≤ n)
        
    Notes:
        - Для ортогонального проектора: dim = rank(P) = trace(P)
        - Численно более устойчиво использовать ранг, а не след
        
    Examples:
        &gt;&gt;&gt; P_xy = subspace_projector([1,0,0], [0,1,0])
        &gt;&gt;&gt; subspace_dimension(P_xy)  # 2
        &gt;&gt;&gt; P_x = vector_projector([1,0,0])
        &gt;&gt;&gt; subspace_dimension(P_x)  # 1
    &quot;&quot;&quot;
    P = numpy.asarray(P)
    
    # Вычисляем ранг через SVD
    s = numpy.linalg.svd(P, compute_uv=False)
    
    if tol is None:
        tol = max(P.shape) * numpy.finfo(P.dtype).eps * s[0] if s.size &gt; 0 else 0
    
    rank = numpy.sum(s &gt; tol)
    
    return int(rank)


def gram_schmidt(*vectors, tol=None):
    &quot;&quot;&quot;Ортогонализует набор векторов классическим методом Грама-Шмидта.
    
    Итеративно строит ортогональный базис: каждый следующий вектор ортогонализуется
    относительно всех предыдущих путём вычитания проекций.
    
    Args:
        *vectors: Набор векторов для ортогонализации.
                  Каждый вектор размера (n,) или (n, 1).
        tol: Порог для определения нулевых векторов (линейная зависимость).
             По умолчанию: машинная_точность * 10
        
    Returns:
        Массив формы (n, k), где k ≤ len(vectors) - количество линейно независимых векторов.
        Столбцы образуют ортонормированный базис span(vectors).
        Если все векторы линейно зависимы, возвращает массив формы (n, 0).
        
    Notes:
        - Классический алгоритм Грама-Шмидта (не модифицированный)
        - Численно менее стабилен чем SVD, особенно для почти коллинеарных векторов
        - Порядок векторов критичен: первые векторы определяют базис
        - Для комплексных векторов использует эрмитово скалярное произведение
        
    Algorithm:
        u₁ = v₁ / ||v₁||
        u₂ = (v₂ - ⟨v₂, u₁⟩u₁) / ||v₂ - ⟨v₂, u₁⟩u₁||
        u₃ = (v₃ - ⟨v₃, u₁⟩u₁ - ⟨v₃, u₂⟩u₂) / ||...||
        ...
        
    Examples:
        &gt;&gt;&gt; v1 = np.array([1., 1., 0.])
        &gt;&gt;&gt; v2 = np.array([1., 0., 0.])
        &gt;&gt;&gt; Q = gram_schmidt(v1, v2)
        &gt;&gt;&gt; np.allclose(Q.T @ Q, np.eye(2))  # Ортонормированность
        True
    &quot;&quot;&quot;
    if len(vectors) == 0:
        raise ValueError(&quot;Необходимо передать хотя бы один вектор&quot;)
    
    # Порог по умолчанию
    if tol is None:
        tol = 10 * numpy.finfo(float).eps
    
    # Преобразуем векторы в массивы-столбцы
    vectors_list = []
    n = None
    for v in vectors:
        v_arr = numpy.asarray(v).flatten()
        if n is None:
            n = len(v_arr)
        elif len(v_arr) != n:
            raise ValueError(f&quot;Все векторы должны иметь одинаковую размерность, получены {n} и {len(v_arr)}&quot;)
        vectors_list.append(v_arr)
    
    # Ортогонализация
    orthonormal_basis = []
    
    for v in vectors_list:
        # Начинаем с исходного вектора
        u = v.copy()
        
        # Вычитаем проекции на все предыдущие ортонормированные векторы
        for q in orthonormal_basis:
            # Проекция: proj_q(u) = ⟨u, q⟩ q
            # Для комплексных: используем vdot (сопряжённое скалярное произведение)
            projection_coef = numpy.vdot(q, u)
            u = u - projection_coef * q
        
        # Нормализуем
        norm = numpy.linalg.norm(u)
        
        # Если вектор стал нулевым (линейно зависим от предыдущих), пропускаем
        if norm &gt; tol:
            u_normalized = u / norm
            orthonormal_basis.append(u_normalized)
    
    # Если нет независимых векторов
    if len(orthonormal_basis) == 0:
        return numpy.empty((n, 0), dtype=vectors_list[0].dtype)
    
    # Собираем в матрицу (векторы = столбцы)
    Q = numpy.column_stack(orthonormal_basis)
    
    return Q


def orthogonalize_svd(*vectors, tol=None):
    &quot;&quot;&quot;Ортогонализует набор векторов через SVD разложение.
    
    Строит ортонормированный базис подпространства, натянутого на входные векторы,
    используя сингулярное разложение (SVD). Численно более стабильный метод,
    чем классический Грам-Шмидт.
    
    Args:
        *vectors: Набор векторов для ортогонализации.
                  Каждый вектор размера (n,) или (n, 1).
        tol: Относительный порог для определения линейной зависимости.
             По умолчанию: max(размеры) * машинная_точность
        
    Returns:
        Массив формы (n, k), где k ≤ len(vectors) - количество линейно независимых векторов.
        Столбцы образуют ортонормированный базис span(vectors).
        Если все векторы нулевые или линейно зависимые от нуля, возвращает массив формы (n, 0).
        
    Notes:
        - Использует SVD для численной устойчивости
        - Порядок векторов НЕ влияет на базис (в отличие от Грама-Шмидта)
        - SVD выбирает &quot;наилучший&quot; базис (главные направления)
        - Векторы базиса ортонормированы: Q.T @ Q = I
        - Для получения проектора: P = Q @ Q.T
        - Более медленный, но более точный чем Грам-Шмидт
        
    Examples:
        &gt;&gt;&gt; v1 = np.array([3., 4., 0.])
        &gt;&gt;&gt; v2 = np.array([1., 0., 1.])
        &gt;&gt;&gt; Q = orthogonalize_svd(v1, v2)
        &gt;&gt;&gt; Q.shape  # (3, 2)
        &gt;&gt;&gt; np.allclose(Q.T @ Q, np.eye(2))  # Ортонормированность
        True
        
        &gt;&gt;&gt; # Линейно зависимые векторы
        &gt;&gt;&gt; v1 = np.array([1., 0., 0.])
        &gt;&gt;&gt; v2 = np.array([2., 0., 0.])  # v2 = 2*v1
        &gt;&gt;&gt; Q = orthogonalize_svd(v1, v2)
        &gt;&gt;&gt; Q.shape  # (3, 1) - только один независимый вектор
    &quot;&quot;&quot;
    if len(vectors) == 0:
        raise ValueError(&quot;Необходимо передать хотя бы один вектор&quot;)
    
    # Преобразуем векторы в массив (векторы = строки)
    vectors_array = [numpy.asarray(v).flatten() for v in vectors]
    A = numpy.vstack(vectors_array)
    
    # SVD разложение
    u, s, vh = numpy.linalg.svd(A, full_matrices=True)
    
    # Определяем порог для линейной независимости
    if tol is None:
        tol = max(A.shape) * numpy.finfo(A.dtype).eps
    
    threshold = tol * s[0] if s.size &gt; 0 else tol
    
    # Ранг = количество значимых сингулярных чисел
    rank = numpy.sum(s &gt; threshold)
    
    # Ортонормированный базис = правые сингулярные векторы для ненулевых σ
    # Транспонируем, чтобы векторы были столбцами
    orthonormal_basis = vh[:rank].T.conj()
    
    return orthonormal_basis


def orthogonalize(*vectors, method='svd', tol=None):
    &quot;&quot;&quot;Ортогонализует набор векторов одним из двух методов.
    
    Универсальная функция ортогонализации с выбором метода.
    
    Args:
        *vectors: Набор векторов для ортогонализации.
                  Каждый вектор размера (n,) или (n, 1).
        method: Метод ортогонализации:
                - 'svd': SVD разложение (по умолчанию, более стабильный)
                - 'gram_schmidt' или 'gs': классический Грам-Шмидт
        tol: Порог для определения линейной зависимости.
             Интерпретация зависит от метода.
        
    Returns:
        Массив формы (n, k), где k ≤ len(vectors).
        Столбцы образуют ортонормированный базис span(vectors).
        
    Notes:
        - SVD: численно стабильный, базис не зависит от порядка векторов
        - Грам-Шмидт: быстрее, но менее стабильный, порядок векторов важен
        
    Examples:
        &gt;&gt;&gt; v1 = np.array([1., 1., 0.])
        &gt;&gt;&gt; v2 = np.array([1., 0., 0.])
        &gt;&gt;&gt; Q_svd = orthogonalize(v1, v2, method='svd')
        &gt;&gt;&gt; Q_gs = orthogonalize(v1, v2, method='gram_schmidt')
        &gt;&gt;&gt; # Оба ортонормированы, но могут давать разные базисы
    &quot;&quot;&quot;
    if method in ('svd', 'SVD'):
        return orthogonalize_svd(*vectors, tol=tol)
    elif method in ('gram_schmidt', 'gs', 'GS', 'Gram-Schmidt'):
        return gram_schmidt(*vectors, tol=tol)
    else:
        raise ValueError(f&quot;Неизвестный метод: {method}. Используйте 'svd' или 'gram_schmidt'&quot;)


def is_projector(P, tol=None):
    &quot;&quot;&quot;Проверяет, является ли матрица ортогональным проектором.
    
    Ортогональный проектор должен удовлетворять двум условиям:
    1. Идемпотентность: P @ P = P
    2. Эрмитовость: P^H = P (для вещественных матриц: P.T = P)
    
    Args:
        P: Матрица для проверки, размер (n, n)
        tol: Порог для численного сравнения.
             По умолчанию: sqrt(n) * машинная_точность * ||P||
        
    Returns:
        True если P - ортогональный проектор, False иначе
        
    Notes:
        - Проверяет обе необходимые характеристики проектора
        - Учитывает численные погрешности через параметр tol
        - Для нулевой матрицы возвращает True (проектор на {0})
        - Дополнительно проверяется, что сингулярные числа ≈ 0 или 1
        
    Examples:
        &gt;&gt;&gt; # Проектор на ось X
        &gt;&gt;&gt; P = vector_projector([1., 0., 0.])
        &gt;&gt;&gt; is_projector(P)
        True
        
        &gt;&gt;&gt; # Обычная матрица (не проектор)
        &gt;&gt;&gt; A = np.array([[1, 2], [3, 4]])
        &gt;&gt;&gt; is_projector(A)
        False
        
        &gt;&gt;&gt; # Проектор на плоскость
        &gt;&gt;&gt; P = subspace_projector([1,0,0], [0,1,0])
        &gt;&gt;&gt; is_projector(P)
        True
    &quot;&quot;&quot;
    P = numpy.asarray(P)
    
    # Проверка квадратности
    if P.ndim != 2 or P.shape[0] != P.shape[1]:
        return False
    
    n = P.shape[0]
    
    # Конвертируем в float для корректной работы с numpy.finfo
    P = _ensure_inexact(P)
    
    # Определяем порог
    if tol is None:
        P_norm = numpy.linalg.norm(P)
        if P_norm == 0:
            return True  # Нулевая матрица - проектор на {0}
        tol = numpy.sqrt(n) * numpy.finfo(P.dtype).eps * P_norm
    
    # 1. Проверка идемпотентности: P @ P = P
    P_squared = P @ P
    idempotent = numpy.allclose(P_squared, P, atol=tol)
    
    if not idempotent:
        return False
    
    # 2. Проверка эрмитовости: P^H = P
    P_hermitian = P.T.conj()
    hermitian = numpy.allclose(P_hermitian, P, atol=tol)
    
    if not hermitian:
        return False
    
    # 3. Дополнительная проверка: сингулярные числа должны быть 0 или 1
    s = numpy.linalg.svd(P, compute_uv=False)
    
    # Более мягкий tolerance для сингулярных чисел
    # (SVD может давать разную точность на разных версиях NumPy/Python)
    svd_tol = max(tol, 10 * numpy.finfo(P.dtype).eps * P_norm)
    
    # Проверяем, что каждое сингулярное число близко либо к 0, либо к 1
    for sigma in s:
        # Расстояние до ближайшего из {0, 1}
        distance_to_binary = min(abs(sigma - 0.0), abs(sigma - 1.0))
        if distance_to_binary &gt; svd_tol:
            return False
    
    return True


def projector_basis(P, rtol=None):
    &quot;&quot;&quot;Извлекает ортонормированный базис подпространства из проектора.
    
    Для проектора P на подпространство V возвращает матрицу Q, столбцы которой
    образуют ортонормированный базис V. Обратная операция: P = Q @ Q.T
    
    Args:
        P: Ортогональный проектор на подпространство, размер (n, n)
        rtol: Относительный порог для определения ранга проектора.
              По умолчанию: max(n) * машинная_точность
        
    Returns:
        Матрица размера (n, k) где k = dim(V) = rank(P).
        Столбцы образуют ортонормированный базис подпространства.
        Если P = 0 (тривиальное подпространство), возвращает массив формы (n, 0).
        
    Notes:
        - Использует SVD разложение проектора
        - Базис извлекается из правых сингулярных векторов
        - Векторы ортонормированы: Q.T @ Q = I_k
        - Проверка: P ≈ Q @ Q.T (с точностью до численных ошибок)
        
    Examples:
        &gt;&gt;&gt; # Создаём проектор на плоскость XY
        &gt;&gt;&gt; P = subspace_projector([1,0,0], [0,1,0])
        &gt;&gt;&gt; Q = projector_basis(P)
        &gt;&gt;&gt; Q.shape  # (3, 2)
        &gt;&gt;&gt; np.allclose(P, Q @ Q.T)  # Восстановление проектора
        True
    &quot;&quot;&quot;
    P = numpy.asarray(P)
    
    # SVD разложение проектора
    u, s, vh = numpy.linalg.svd(P, full_matrices=True)
    
    # Определяем порог
    if rtol is None:
        rtol = max(P.shape) * numpy.finfo(P.dtype).eps
    
    threshold = rtol * s[0] if s.size &gt; 0 else rtol
    
    # Ранг = количество значимых сингулярных чисел
    rank = numpy.sum(s &gt; threshold)
    
    if rank == 0:
        # Тривиальное подпространство {0}
        return numpy.empty((P.shape[0], 0), dtype=P.dtype)
    
    # Базис = правые сингулярные векторы для ненулевых σ
    # (транспонируем, чтобы векторы были столбцами)
    basis = vh[:rank].T.conj()
    
    return basis


def subspace_intersection(P1, P2, tol=None):
    &quot;&quot;&quot;Возвращает проектор на пересечение двух подпространств.
    
    Вычисляет проектор на V1 ∩ V2, где V1 и V2 заданы проекторами P1 и P2.
    Использует метод через нуль-пространство: V1 ∩ V2 = V1 ∩ ker(I - P2).
    
    Args:
        P1: Проектор на первое подпространство V1, размер (n, n)
        P2: Проектор на второе подпространство V2, размер (n, n)
        tol: Порог для определения линейной зависимости.
             По умолчанию: max(n) * машинная_точность
        
    Returns:
        Матрица проектора на пересечение V1 ∩ V2, размер (n, n)
        
    Notes:
        - Если подпространства не пересекаются (только в 0), возвращает нулевой проектор
        - Метод: находим базис V1, проецируем на V2, ищем векторы, оставшиеся в V1
        - Математически: v ∈ V1 ∩ V2 ⟺ v ∈ V1 и P2 @ v = v
        - dim(V1 ∩ V2) ≤ min(dim(V1), dim(V2))
        - Для ортогональных подпространств: V1 ∩ V2 = {0}
        
    Examples:
        &gt;&gt;&gt; # Плоскость XY и плоскость XZ пересекаются по оси X
        &gt;&gt;&gt; P_xy = subspace_projector([1,0,0], [0,1,0])
        &gt;&gt;&gt; P_xz = subspace_projector([1,0,0], [0,0,1])
        &gt;&gt;&gt; P_x = subspace_intersection(P_xy, P_xz)
        &gt;&gt;&gt; # P_x - проектор на ось X (dim = 1)
        
        &gt;&gt;&gt; # Ортогональные подпространства
        &gt;&gt;&gt; P_x = vector_projector([1,0,0])
        &gt;&gt;&gt; P_y = vector_projector([0,1,0])
        &gt;&gt;&gt; P_int = subspace_intersection(P_x, P_y)
        &gt;&gt;&gt; # P_int ≈ 0 (пересечение пустое)
    &quot;&quot;&quot;
    P1 = numpy.asarray(P1)
    P2 = numpy.asarray(P2)
    
    if P1.shape != P2.shape:
        raise ValueError(f&quot;Проекторы должны иметь одинаковый размер, получены {P1.shape} и {P2.shape}&quot;)
    
    # Извлекаем базис V1 из проектора P1
    basis1 = projector_basis(P1, rtol=tol)
    
    if basis1.size == 0:
        # V1 = {0}, пересечение пустое
        return numpy.zeros_like(P1)
    
    # Проецируем базисные векторы V1 на V2
    # Вектор v ∈ V1 лежит в V1 ∩ V2 ⟺ P2 @ v = v
    projected_basis = P2 @ basis1
    
    # Разность: (P2 @ v - v) должна быть нулевой для векторов из пересечения
    diff = projected_basis - basis1
    
    # Находим нуль-пространство diff (линейные комбинации столбцов basis1,
    # которые не изменяются при проекции на V2)
    # diff @ c ≈ 0  =&gt;  c задаёт вектор из пересечения
    
    # Определяем абсолютный порог для сингулярных чисел
    # Используем норму базиса как характерный масштаб
    if tol is None:
        tol = max(P1.shape) * numpy.finfo(P1.dtype).eps
    
    # Абсолютный порог учитывает масштаб задачи
    threshold = tol * max(1.0, numpy.linalg.norm(basis1))
    
    # Используем существующую функцию с абсолютным порогом
    null_coefs = nullspace_basis(diff, atol=threshold)
    
    if null_coefs.size == 0:
        # Пересечение пустое (только нулевой вектор)
        return numpy.zeros_like(P1)
    
    # Строим базис пересечения: линейные комбинации basis1
    intersection_basis = basis1 @ null_coefs
    
    # Проектор = базис @ базис^H
    return intersection_basis @ intersection_basis.T.conj()


def project_onto_affine(x, C, b):
    &quot;&quot;&quot;Возвращает ортогональную проекцию вектора x на аффинное множество, заданное C @ y = b.
    
    Args:
        x: Вектор размера (n,)
        C: Линейно-независимая матрица размера (m, n), задающая линейное отображение
        b: Вектор размера (m,), задающий сдвиг аффинного множества

    Returns:
        Вектор размера (n,) - проекция x на множество {y | C @ y = b}
    &quot;&quot;&quot;

    x = numpy.asarray(x).flatten()
    C = numpy.asarray(C)
    b = numpy.asarray(b).flatten()
    
    if C.shape[0] != b.shape[0]:
        raise ValueError(f&quot;Размерность b должна соответствовать числу строк C, получены {C.shape[0]} и {b.shape[0]}&quot;)
    if C.shape[1] != x.shape[0]:
        raise ValueError(f&quot;Размерность x должна соответствовать числу столбцов C, получены {C.shape[1]} и {x.shape[0]}&quot;)
    
    Ct = C.T.conj()
    CCt_inv = numpy.linalg.pinv(C @ Ct)
    projection = x - Ct @ (CCt_inv @ (C @ x - b))
    return projection

def affine_projector(C, b):
    &quot;&quot;&quot;Возвращает проектор на аффинное множество A, заданное C @ y = b и вектор смещения B:

    Решение следует подставлять в форму x^ = x - (A.x - B).
    Здесь
    A = C.T @ (C @ C.T)^(-1) @ C
    B = C.T @ (C @ C.T)^(-1) @ b
    &quot;&quot;&quot;
    C = numpy.asarray(C)
    b = numpy.asarray(b).flatten()
    
    if C.shape[0] != b.shape[0]:
        raise ValueError(f&quot;Размерность b должна соответствовать числу строк C, получены {C.shape[0]} и {b.shape[0]}&quot;)
    
    Ct = C.T.conj()
    CCt_inv = numpy.linalg.pinv(C @ Ct)
    
    K = Ct @ CCt_inv
    A = K @ C
    B = K @ b

    return A, B

def metric_project_onto_constraints(
        q: numpy.ndarray, 
        H: numpy.ndarray,
        M_inv: numpy.ndarray,
        error: numpy.ndarray = None,
        h: numpy.ndarray = None) -&gt; numpy.ndarray:
    &quot;&quot;&quot;Проецировать скорости на ограничения
    
    q - текущий вектор
    H - матрица ограничений
    M_inv - метрическая матрица
    
    Одно из двух должно быть задано:
        error - текущая ошибка
        h - правая часть ограничений
    &quot;&quot;&quot;
    if error is None:
        error = H @ q - h

    S = H @ M_inv @ H.T

    lmbda = numpy.linalg.solve(S, error)
    corrected = q - M_inv @ H.T @ lmbda

    return corrected 

</code></pre>
</body>
</html>
