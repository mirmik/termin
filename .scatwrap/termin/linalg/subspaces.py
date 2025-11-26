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
    &quot;&quot;&quot;Конвертирует целочисленные массивы в float, сохраняя float/complex типы.&quot;&quot;&quot;<br>
    A = numpy.asarray(A)<br>
    if not numpy.issubdtype(A.dtype, numpy.inexact):<br>
        # Конвертируем целые числа в float64<br>
        return numpy.asarray(A, dtype=float)<br>
    # Оставляем float32/float64/complex как есть<br>
    return A<br>
<br>
<br>
def nullspace_projector(A):<br>
    &quot;&quot;&quot;Возвращает матрицу ортогонального проектора на нуль-пространство матрицы A.<br>
    <br>
    Проектор P обладает свойствами:<br>
    - A @ P = 0 (проекция попадает в нуль-пространство)<br>
    - P @ P = P (идемпотентность)<br>
    - P.T = P (для вещественных матриц - симметричность)<br>
    <br>
    Args:<br>
        A: Матрица размера (m, n)<br>
        <br>
    Returns:<br>
        Матрица проектора размера (n, n)<br>
        <br>
    Notes:<br>
        Для проекции вектора v на нуль-пространство: v_proj = P @ v<br>
        Использует SVD-разложение для оптимальной производительности.<br>
    &quot;&quot;&quot;<br>
    A = _ensure_inexact(A)<br>
    u, s, vh = numpy.linalg.svd(A, full_matrices=True)<br>
    <br>
    # Определяем ранг матрицы<br>
    tol = max(A.shape) * numpy.finfo(A.dtype).eps * s[0] if s.size &gt; 0 else 0<br>
    rank = numpy.sum(s &gt; tol)<br>
    <br>
    # Базис нуль-пространства = правые сингулярные векторы для нулевых сингулярных чисел<br>
    null_basis = vh[rank:].T.conj()<br>
    <br>
    # Проектор = базис @ базис.T<br>
    if null_basis.size &gt; 0:<br>
        return null_basis @ null_basis.T.conj()<br>
    else:<br>
        # Нуль-пространство пустое - возвращаем нулевой проектор<br>
        return numpy.zeros((A.shape[1], A.shape[1]), dtype=A.dtype)<br>
<br>
<br>
def nullspace_basis_svd(A, rtol=None, atol=None):<br>
    &quot;&quot;&quot;Ортонормированный базис ker(A), полученный через SVD A = U Σ V^H.<br>
<br>
    Правые сингулярные векторы, соответствующие нулевым σ, образуют базис<br>
    нуль-пространства. В реализации отбрасываются σ ниже заданного порога.<br>
<br>
    Args:<br>
        A: Матрица размера (m, n)<br>
        rtol: Относительный порог для сингулярных чисел (≈ eps · max(m, n)).<br>
        atol: Абсолютный порог (если задан, имеет приоритет над rtol).<br>
<br>
    Returns:<br>
        Матрица (n, k) с ортонормированными столбцами basis, где A @ basis = 0.<br>
        Если ker(A) тривиально, возвращается массив формы (n, 0).<br>
    &quot;&quot;&quot;<br>
    A = _ensure_inexact(A)<br>
    u, s, vh = numpy.linalg.svd(A, full_matrices=True)<br>
<br>
    if atol is not None:<br>
        tol = atol<br>
    else:<br>
        if rtol is None:<br>
            rtol = max(A.shape) * numpy.finfo(A.dtype).eps<br>
        tol = rtol * s[0] if s.size &gt; 0 else rtol<br>
<br>
    rank = numpy.sum(s &gt; tol)<br>
    null_basis = vh[rank:].T.conj()<br>
<br>
    if null_basis.size == 0:<br>
        return numpy.zeros((A.shape[1], 0), dtype=A.dtype)<br>
<br>
    return null_basis<br>
<br>
<br>
def nullspace_basis_qr(A, rtol=None, atol=None):<br>
    &quot;&quot;&quot;Ортонормированный базис ker(A) по формуле A^T = Q R (полный QR).<br>
<br>
    Если r = rank(A), то строки A лежат в span(Q[:, :r]) и<br>
    ker(A) = (rowspace(A))^⊥ = span(Q[:, r:]). Хвостовые столбцы Q уже<br>
    ортонормированы и задают искомый базис.<br>
<br>
    Args:<br>
        A: Матрица размера (m, n)<br>
        rtol: Относительный порог для диагонали R.<br>
        atol: Абсолютный порог (если задан, имеет приоритет).<br>
<br>
    Returns:<br>
        Матрица (n, k) с ортонормированными столбцами ker(A).<br>
        Если дополнение тривиально, возвращается массив формы (n, 0).<br>
    &quot;&quot;&quot;<br>
    A = _ensure_inexact(A)<br>
    m, n = A.shape<br>
<br>
    if n == 0:<br>
        return numpy.zeros((0, 0), dtype=A.dtype)<br>
<br>
    Q, R = numpy.linalg.qr(A.T, mode=&quot;complete&quot;)<br>
    diag_len = min(n, m)<br>
<br>
    if diag_len == 0:<br>
        rank = 0<br>
    else:<br>
        diag = numpy.abs(numpy.diag(R[:diag_len, :diag_len]))<br>
        max_diag = diag.max() if diag.size &gt; 0 else 0.0<br>
<br>
        if atol is not None:<br>
            tol = atol<br>
        else:<br>
            if rtol is None:<br>
                rtol = max(m, n) * numpy.finfo(A.dtype).eps<br>
            tol = rtol * max_diag if max_diag &gt; 0 else rtol<br>
<br>
        rank = int(numpy.sum(diag &gt; tol))<br>
<br>
    return Q[:, rank:]<br>
<br>
<br>
def nullspace_basis(A, rtol=None, atol=None, method=&quot;svd&quot;):<br>
    &quot;&quot;&quot;Возвращает ортонормированный базис ker(A) с выбранным алгоритмом.<br>
<br>
    Args:<br>
        A: Матрица размера (m, n)<br>
        rtol: Относительный порог толеранса.<br>
        atol: Абсолютный порог толеранса.<br>
        method: 'svd' (устойчивее) или 'qr' (быстрее для узких матриц).<br>
<br>
    Returns:<br>
        Матрица (n, k), столбцы которой образуют базис нуль-пространства.<br>
<br>
    Raises:<br>
        ValueError: если указан неподдерживаемый method.<br>
    &quot;&quot;&quot;<br>
    if method is None:<br>
        method = &quot;svd&quot;<br>
<br>
    if method == &quot;svd&quot;:<br>
        return nullspace_basis_svd(A, rtol=rtol, atol=atol)<br>
    if method == &quot;qr&quot;:<br>
        return nullspace_basis_qr(A, rtol=rtol, atol=atol)<br>
<br>
    raise ValueError(f&quot;Unsupported nullspace method '{method}'. Use 'svd' or 'qr'.&quot;)<br>
<br>
<br>
def rowspace_projector(A):<br>
    &quot;&quot;&quot;Возвращает матрицу ортогонального проектора на пространство строк матрицы A.<br>
    <br>
    Пространство строк (row space) - это ортогональное дополнение к нуль-пространству.<br>
    Проектор P обладает свойствами:<br>
    - P @ v лежит в пространстве строк для любого v<br>
    - P + nullspace_projector(A) = I (дополнение)<br>
    - P @ P = P (идемпотентность)<br>
    - P.T = P (для вещественных матриц - симметричность)<br>
    <br>
    Args:<br>
        A: Матрица размера (m, n)<br>
        <br>
    Returns:<br>
        Матрица проектора размера (n, n)<br>
        <br>
    Notes:<br>
        Для проекции вектора v на пространство строк: v_proj = P @ v<br>
        rowspace_projector(A) = I - nullspace_projector(A)<br>
    &quot;&quot;&quot;<br>
    A = _ensure_inexact(A)<br>
    u, s, vh = numpy.linalg.svd(A, full_matrices=True)<br>
    <br>
    # Определяем ранг матрицы<br>
    tol = max(A.shape) * numpy.finfo(A.dtype).eps * s[0] if s.size &gt; 0 else 0<br>
    rank = numpy.sum(s &gt; tol)<br>
    <br>
    # Базис пространства строк = правые сингулярные векторы для ненулевых σ<br>
    row_basis = vh[:rank].T.conj()<br>
    <br>
    # Проектор = базис @ базис.T<br>
    if row_basis.size &gt; 0:<br>
        return row_basis @ row_basis.T.conj()<br>
    else:<br>
        # Пространство строк пустое - возвращаем нулевой проектор<br>
        return numpy.zeros((A.shape[1], A.shape[1]), dtype=A.dtype)<br>
<br>
<br>
def rowspace_basis(A, rtol=None):<br>
    &quot;&quot;&quot;Возвращает ортонормированный базис пространства строк матрицы A.<br>
    <br>
    Пространство строк (row space) состоит из всех линейных комбинаций строк A.<br>
    Это ортогональное дополнение к нуль-пространству: rowspace ⊕ nullspace = R^n.<br>
    <br>
    Args:<br>
        A: Матрица размера (m, n)<br>
        rtol: Относительный порог для определения нулевых сингулярных чисел.<br>
              По умолчанию: max(m, n) * машинная_точность * max(сингулярное_число)<br>
        <br>
    Returns:<br>
        Матрица размера (n, k) где k = rank(A) - размерность пространства строк.<br>
        Столбцы образуют ортонормированный базис пространства строк.<br>
        Если rank(A) = 0, возвращает массив формы (n, 0).<br>
    <br>
    Notes:<br>
        - Использует SVD-разложение для численной устойчивости<br>
        - Размерность пространства строк = rank(A)<br>
        - Векторы базиса ортонормированы: basis.T @ basis = I<br>
        - Для получения проектора: P = basis @ basis.T<br>
        - Дополнение: rowspace_basis ⊕ nullspace_basis = полный базис R^n<br>
    <br>
    Examples:<br>
        &gt;&gt;&gt; A = np.array([[1, 2, 3], [2, 4, 6]])  # Ранг 1<br>
        &gt;&gt;&gt; R = rowspace_basis(A)<br>
        &gt;&gt;&gt; R.shape  # (3, 1) - базис из 1 вектора<br>
        &gt;&gt;&gt; N = nullspace_basis(A)<br>
        &gt;&gt;&gt; N.shape  # (3, 2) - дополнение<br>
    &quot;&quot;&quot;<br>
    A = _ensure_inexact(A)<br>
    u, s, vh = numpy.linalg.svd(A, full_matrices=True)<br>
    <br>
    # Определяем порог для малых сингулярных чисел<br>
    if rtol is None:<br>
        rtol = max(A.shape) * numpy.finfo(A.dtype).eps<br>
    <br>
    tol = rtol * s[0] if s.size &gt; 0 else rtol<br>
    <br>
    # Ранг матрицы = количество сингулярных чисел больше порога<br>
    rank = numpy.sum(s &gt; tol)<br>
    <br>
    # Пространство строк = правые сингулярные векторы соответствующие ненулевым σ<br>
    # Берём строки vh с индексами [:rank] и транспонируем<br>
    row_basis = vh[:rank].T.conj()<br>
    <br>
    return row_basis<br>
<br>
<br>
def colspace_projector(A):<br>
    &quot;&quot;&quot;Возвращает матрицу ортогонального проектора на пространство столбцов матрицы A.<br>
    <br>
    Пространство столбцов (column space, range) - это образ отображения A.<br>
    Проектор P обладает свойствами:<br>
    - P @ b лежит в colspace для любого b<br>
    - P + left_nullspace_projector(A) = I (дополнение)<br>
    - P @ P = P (идемпотентность)<br>
    - P.T = P (для вещественных матриц - симметричность)<br>
    <br>
    Args:<br>
        A: Матрица размера (m, n)<br>
        <br>
    Returns:<br>
        Матрица проектора размера (m, m)<br>
        <br>
    Notes:<br>
        Для проекции вектора b на пространство столбцов: b_proj = P @ b<br>
        Если Ax = b несовместна, то Ax = P @ b всегда разрешима.<br>
        Работает в пространстве значений R^m.<br>
    &quot;&quot;&quot;<br>
    A = _ensure_inexact(A)<br>
    u, s, vh = numpy.linalg.svd(A, full_matrices=True)<br>
    <br>
    # Определяем ранг матрицы<br>
    tol = max(A.shape) * numpy.finfo(A.dtype).eps * s[0] if s.size &gt; 0 else 0<br>
    rank = numpy.sum(s &gt; tol)<br>
    <br>
    # Базис пространства столбцов = левые сингулярные векторы для ненулевых σ<br>
    col_basis = u[:, :rank]<br>
    <br>
    # Проектор = базис @ базис.T<br>
    if col_basis.size &gt; 0:<br>
        return col_basis @ col_basis.T.conj()<br>
    else:<br>
        # Пространство столбцов пустое - возвращаем нулевой проектор<br>
        return numpy.zeros((A.shape[0], A.shape[0]), dtype=A.dtype)<br>
<br>
<br>
def colspace_basis(A, rtol=None):<br>
    &quot;&quot;&quot;Возвращает ортонормированный базис пространства столбцов матрицы A.<br>
    <br>
    Пространство столбцов (column space, range, образ) состоит из всех векторов вида A @ x.<br>
    Это ортогональное дополнение к левому нуль-пространству: colspace ⊕ left_nullspace = R^m.<br>
    <br>
    Args:<br>
        A: Матрица размера (m, n)<br>
        rtol: Относительный порог для определения нулевых сингулярных чисел.<br>
              По умолчанию: max(m, n) * машинная_точность * max(сингулярное_число)<br>
        <br>
    Returns:<br>
        Матрица размера (m, k) где k = rank(A) - размерность пространства столбцов.<br>
        Столбцы образуют ортонормированный базис пространства столбцов.<br>
        Если rank(A) = 0, возвращает массив формы (m, 0).<br>
    <br>
    Notes:<br>
        - Использует SVD-разложение для численной устойчивости<br>
        - Размерность пространства столбцов = rank(A)<br>
        - Векторы базиса ортонормированы: basis.T @ basis = I<br>
        - Для получения проектора: P = basis @ basis.T<br>
        - Работает в пространстве значений R^m<br>
        - Эквивалент scipy.linalg.orth(A)<br>
    <br>
    Examples:<br>
        &gt;&gt;&gt; A = np.array([[1, 0], [2, 0], [3, 0]])  # Ранг 1<br>
        &gt;&gt;&gt; C = colspace_basis(A)<br>
        &gt;&gt;&gt; C.shape  # (3, 1) - базис из 1 вектора<br>
        &gt;&gt;&gt; # Любой вектор A @ x лежит в span(C)<br>
    &quot;&quot;&quot;<br>
    A = _ensure_inexact(A)<br>
    u, s, vh = numpy.linalg.svd(A, full_matrices=True)<br>
    <br>
    # Определяем порог для малых сингулярных чисел<br>
    if rtol is None:<br>
        rtol = max(A.shape) * numpy.finfo(A.dtype).eps<br>
    <br>
    tol = rtol * s[0] if s.size &gt; 0 else rtol<br>
    <br>
    # Ранг матрицы = количество сингулярных чисел больше порога<br>
    rank = numpy.sum(s &gt; tol)<br>
    <br>
    # Пространство столбцов = левые сингулярные векторы соответствующие ненулевым σ<br>
    col_basis = u[:, :rank]<br>
    <br>
    return col_basis<br>
<br>
<br>
def left_nullspace_projector(A):<br>
    &quot;&quot;&quot;Возвращает матрицу ортогонального проектора на левое нуль-пространство матрицы A.<br>
    <br>
    Левое нуль-пространство состоит из векторов y таких, что A^T @ y = 0.<br>
    Это ортогональное дополнение к пространству столбцов.<br>
    Проектор P обладает свойствами:<br>
    - A^T @ P = 0 (эквивалентно: P @ A = 0)<br>
    - P + colspace_projector(A) = I (дополнение)<br>
    - P @ P = P (идемпотентность)<br>
    - P.T = P (для вещественных матриц - симметричность)<br>
    <br>
    Args:<br>
        A: Матрица размера (m, n)<br>
        <br>
    Returns:<br>
        Матрица проектора размера (m, m)<br>
        <br>
    Notes:<br>
        Для проекции вектора b на левое нуль-пространство: b_proj = P @ b<br>
        left_nullspace(A) = nullspace(A^T)<br>
        Работает в пространстве значений R^m.<br>
    &quot;&quot;&quot;<br>
    A = _ensure_inexact(A)<br>
    u, s, vh = numpy.linalg.svd(A, full_matrices=True)<br>
    <br>
    # Определяем ранг матрицы<br>
    tol = max(A.shape) * numpy.finfo(A.dtype).eps * s[0] if s.size &gt; 0 else 0<br>
    rank = numpy.sum(s &gt; tol)<br>
    <br>
    # Базис левого нуль-пространства = левые сингулярные векторы для нулевых σ<br>
    left_null_basis = u[:, rank:]<br>
    <br>
    # Проектор = базис @ базис.T<br>
    if left_null_basis.size &gt; 0:<br>
        return left_null_basis @ left_null_basis.T.conj()<br>
    else:<br>
        # Левое нуль-пространство пустое - возвращаем нулевой проектор<br>
        return numpy.zeros((A.shape[0], A.shape[0]), dtype=A.dtype)<br>
<br>
<br>
def left_nullspace_basis(A, rtol=None):<br>
    &quot;&quot;&quot;Возвращает ортонормированный базис левого нуль-пространства матрицы A.<br>
    <br>
    Левое нуль-пространство состоит из векторов y таких, что A^T @ y = 0.<br>
    Это ортогональное дополнение к пространству столбцов: left_nullspace ⊕ colspace = R^m.<br>
    <br>
    Args:<br>
        A: Матрица размера (m, n)<br>
        rtol: Относительный порог для определения нулевых сингулярных чисел.<br>
              По умолчанию: max(m, n) * машинная_точность * max(сингулярное_число)<br>
        <br>
    Returns:<br>
        Матрица размера (m, k) где k = m - rank(A) - размерность левого нуль-пространства.<br>
        Столбцы образуют ортонормированный базис левого нуль-пространства.<br>
        Если rank(A) = m, возвращает массив формы (m, 0).<br>
    <br>
    Notes:<br>
        - Использует SVD-разложение для численной устойчивости<br>
        - Размерность левого нуль-пространства = m - rank(A)<br>
        - Векторы базиса ортонормированы: basis.T @ basis = I<br>
        - Для получения проектора: P = basis @ basis.T<br>
        - Работает в пространстве значений R^m<br>
        - Эквивалент nullspace_basis(A.T)<br>
    <br>
    Examples:<br>
        &gt;&gt;&gt; A = np.array([[1, 2], [2, 4], [3, 6]])  # Ранг 1<br>
        &gt;&gt;&gt; L = left_nullspace_basis(A)<br>
        &gt;&gt;&gt; L.shape  # (3, 2) - базис из 2 векторов<br>
        &gt;&gt;&gt; np.allclose(A.T @ L, 0)  # Проверка: A^T @ y = 0<br>
        True<br>
    &quot;&quot;&quot;<br>
    A = _ensure_inexact(A)<br>
    u, s, vh = numpy.linalg.svd(A, full_matrices=True)<br>
    <br>
    # Определяем порог для малых сингулярных чисел<br>
    if rtol is None:<br>
        rtol = max(A.shape) * numpy.finfo(A.dtype).eps<br>
    <br>
    tol = rtol * s[0] if s.size &gt; 0 else rtol<br>
    <br>
    # Ранг матрицы = количество сингулярных чисел больше порога<br>
    rank = numpy.sum(s &gt; tol)<br>
    <br>
    # Левое нуль-пространство = левые сингулярные векторы соответствующие нулевым σ<br>
    left_null_basis = u[:, rank:]<br>
    <br>
    return left_null_basis<br>
<br>
<br>
def vector_projector(u):<br>
    &quot;&quot;&quot;Возвращает матрицу ортогонального проектора на направление вектора u.<br>
    <br>
    Проектор P проецирует любой вектор v на направление u:<br>
        P @ v = proj_u(v) = (u · v / u · u) * u<br>
    <br>
    Args:<br>
        u: Вектор-направление размера (n,) или (n, 1)<br>
        <br>
    Returns:<br>
        Матрица проектора размера (n, n)<br>
        <br>
    Raises:<br>
        ValueError: Если u - нулевой вектор<br>
        <br>
    Notes:<br>
        Проектор имеет вид: P = (u @ u.T) / (u.T @ u)<br>
        Свойства:<br>
        - P @ P = P (идемпотентность)<br>
        - P.T = P (симметричность для вещественных векторов)<br>
        - rank(P) = 1<br>
        - trace(P) = 1<br>
    <br>
    Examples:<br>
        &gt;&gt;&gt; u = np.array([1., 0., 0.])  # Вектор вдоль оси X<br>
        &gt;&gt;&gt; P = vector_projector(u)<br>
        &gt;&gt;&gt; v = np.array([3., 4., 5.])<br>
        &gt;&gt;&gt; P @ v  # array([3., 0., 0.]) - проекция на ось X<br>
    &quot;&quot;&quot;<br>
    u = numpy.asarray(u)<br>
    <br>
    # Приводим к вектору-столбцу<br>
    if u.ndim == 1:<br>
        u = u.reshape(-1, 1)<br>
    elif u.ndim == 2 and u.shape[1] != 1:<br>
        raise ValueError(f&quot;u должен быть вектором, получена матрица формы {u.shape}&quot;)<br>
    <br>
    # Проверка на нулевой вектор<br>
    norm_sq = numpy.vdot(u, u).real  # u^H @ u для комплексных векторов<br>
    if norm_sq == 0:<br>
        raise ValueError(&quot;Нельзя проецировать на нулевой вектор&quot;)<br>
    <br>
    # P = u @ u^H / (u^H @ u)<br>
    return (u @ u.T.conj()) / norm_sq<br>
<br>
<br>
def subspace_projector(*vectors):<br>
    &quot;&quot;&quot;Возвращает матрицу ортогонального проектора на подпространство, натянутое на векторы.<br>
    <br>
    Проектор P проецирует любой вектор v на подпространство span(u1, u2, ..., uk):<br>
        P @ v = проекция v на span(vectors)<br>
    <br>
    Args:<br>
        *vectors: Набор векторов, задающих подпространство.<br>
                  Каждый вектор размера (n,) или (n, 1).<br>
                  Векторы могут быть линейно зависимы (автоматически учитывается).<br>
        <br>
    Returns:<br>
        Матрица проектора размера (n, n)<br>
        <br>
    Raises:<br>
        ValueError: Если все векторы нулевые или не переданы<br>
        <br>
    Notes:<br>
        - Автоматически ортогонализует векторы через SVD<br>
        - Ранг проектора = rank(span(vectors))<br>
        - Работает для любого количества векторов (k-векторы, бивекторы и т.д.)<br>
        - Для 1 вектора эквивалентно vector_projector()<br>
        - Для 2 векторов - проектор на плоскость (бивектор)<br>
        <br>
    Examples:<br>
        &gt;&gt;&gt; # Проектор на плоскость XY<br>
        &gt;&gt;&gt; u1 = np.array([1., 0., 0.])<br>
        &gt;&gt;&gt; u2 = np.array([0., 1., 0.])<br>
        &gt;&gt;&gt; P = subspace_projector(u1, u2)<br>
        &gt;&gt;&gt; v = np.array([3., 4., 5.])<br>
        &gt;&gt;&gt; P @ v  # array([3., 4., 0.]) - проекция на XY<br>
    &quot;&quot;&quot;<br>
    if len(vectors) == 0:<br>
        raise ValueError(&quot;Необходимо передать хотя бы один вектор&quot;)<br>
    <br>
    # Собираем векторы в матрицу (каждый вектор - строка)<br>
    vectors_array = [numpy.asarray(v).flatten() for v in vectors]<br>
    A = numpy.vstack(vectors_array)<br>
    <br>
    # Используем rowspace_projector - он уже делает всё нужное:<br>
    # - SVD разложение<br>
    # - Учёт линейной зависимости<br>
    # - Ортогонализацию<br>
    return rowspace_projector(A)<br>
<br>
<br>
def orthogonal_complement(P):<br>
    &quot;&quot;&quot;Возвращает проектор на ортогональное дополнение подпространства.<br>
    <br>
    Если P - проектор на подпространство V, то (I - P) - проектор на V⊥.<br>
    <br>
    Args:<br>
        P: Матрица ортогонального проектора размера (n, n)<br>
        <br>
    Returns:<br>
        Матрица проектора на ортогональное дополнение размера (n, n)<br>
        <br>
    Notes:<br>
        - P + orthogonal_complement(P) = I<br>
        - Работает для любого ортогонального проектора<br>
        - dim(V) + dim(V⊥) = n<br>
        <br>
    Examples:<br>
        &gt;&gt;&gt; # Проектор на ось X<br>
        &gt;&gt;&gt; P_x = subspace_projector([1., 0., 0.])<br>
        &gt;&gt;&gt; P_perp = orthogonal_complement(P_x)<br>
        &gt;&gt;&gt; # P_perp проецирует на плоскость YZ<br>
    &quot;&quot;&quot;<br>
    P = numpy.asarray(P)<br>
    n = P.shape[0]<br>
    return numpy.eye(n, dtype=P.dtype) - P<br>
<br>
<br>
def is_in_subspace(v, P, tol=None):<br>
    &quot;&quot;&quot;Проверяет, принадлежит ли вектор подпространству.<br>
    <br>
    Вектор v ∈ V &lt;=&gt; P @ v = v (проекция совпадает с исходным вектором).<br>
    <br>
    Args:<br>
        v: Вектор размера (n,) или (n, 1)<br>
        P: Проектор на подпространство V, размер (n, n)<br>
        tol: Порог для сравнения ||P @ v - v||. <br>
             По умолчанию: sqrt(n) * машинная_точность * ||v||<br>
        <br>
    Returns:<br>
        True если v ∈ V, False иначе<br>
        <br>
    Notes:<br>
        - Численно устойчиво для малых возмущений<br>
        - Для нулевого вектора всегда возвращает True<br>
        <br>
    Examples:<br>
        &gt;&gt;&gt; P_xy = subspace_projector([1,0,0], [0,1,0])<br>
        &gt;&gt;&gt; is_in_subspace([3, 4, 0], P_xy)  # True<br>
        &gt;&gt;&gt; is_in_subspace([3, 4, 5], P_xy)  # False<br>
    &quot;&quot;&quot;<br>
    v = numpy.asarray(v).flatten()<br>
    P = numpy.asarray(P)<br>
    <br>
    # Проецируем вектор<br>
    projected = P @ v<br>
    <br>
    # Вычисляем разность<br>
    diff = projected - v<br>
    diff_norm = numpy.linalg.norm(diff)<br>
    <br>
    # Порог по умолчанию<br>
    if tol is None:<br>
        v_norm = numpy.linalg.norm(v)<br>
        if v_norm == 0:<br>
            return True  # Нулевой вектор всегда в подпространстве<br>
        tol = numpy.sqrt(len(v)) * numpy.finfo(P.dtype).eps * v_norm<br>
    <br>
    return diff_norm &lt;= tol<br>
<br>
<br>
def subspace_dimension(P, tol=None):<br>
    &quot;&quot;&quot;Возвращает размерность подпространства, заданного проектором.<br>
    <br>
    Размерность = ранг проектора = след проектора.<br>
    <br>
    Args:<br>
        P: Проектор на подпространство, размер (n, n)<br>
        tol: Порог для определения ненулевых сингулярных чисел.<br>
             По умолчанию: n * машинная_точность * max(сингулярное_число)<br>
        <br>
    Returns:<br>
        Целое число - размерность подпространства (0 ≤ dim ≤ n)<br>
        <br>
    Notes:<br>
        - Для ортогонального проектора: dim = rank(P) = trace(P)<br>
        - Численно более устойчиво использовать ранг, а не след<br>
        <br>
    Examples:<br>
        &gt;&gt;&gt; P_xy = subspace_projector([1,0,0], [0,1,0])<br>
        &gt;&gt;&gt; subspace_dimension(P_xy)  # 2<br>
        &gt;&gt;&gt; P_x = vector_projector([1,0,0])<br>
        &gt;&gt;&gt; subspace_dimension(P_x)  # 1<br>
    &quot;&quot;&quot;<br>
    P = numpy.asarray(P)<br>
    <br>
    # Вычисляем ранг через SVD<br>
    s = numpy.linalg.svd(P, compute_uv=False)<br>
    <br>
    if tol is None:<br>
        tol = max(P.shape) * numpy.finfo(P.dtype).eps * s[0] if s.size &gt; 0 else 0<br>
    <br>
    rank = numpy.sum(s &gt; tol)<br>
    <br>
    return int(rank)<br>
<br>
<br>
def gram_schmidt(*vectors, tol=None):<br>
    &quot;&quot;&quot;Ортогонализует набор векторов классическим методом Грама-Шмидта.<br>
    <br>
    Итеративно строит ортогональный базис: каждый следующий вектор ортогонализуется<br>
    относительно всех предыдущих путём вычитания проекций.<br>
    <br>
    Args:<br>
        *vectors: Набор векторов для ортогонализации.<br>
                  Каждый вектор размера (n,) или (n, 1).<br>
        tol: Порог для определения нулевых векторов (линейная зависимость).<br>
             По умолчанию: машинная_точность * 10<br>
        <br>
    Returns:<br>
        Массив формы (n, k), где k ≤ len(vectors) - количество линейно независимых векторов.<br>
        Столбцы образуют ортонормированный базис span(vectors).<br>
        Если все векторы линейно зависимы, возвращает массив формы (n, 0).<br>
        <br>
    Notes:<br>
        - Классический алгоритм Грама-Шмидта (не модифицированный)<br>
        - Численно менее стабилен чем SVD, особенно для почти коллинеарных векторов<br>
        - Порядок векторов критичен: первые векторы определяют базис<br>
        - Для комплексных векторов использует эрмитово скалярное произведение<br>
        <br>
    Algorithm:<br>
        u₁ = v₁ / ||v₁||<br>
        u₂ = (v₂ - ⟨v₂, u₁⟩u₁) / ||v₂ - ⟨v₂, u₁⟩u₁||<br>
        u₃ = (v₃ - ⟨v₃, u₁⟩u₁ - ⟨v₃, u₂⟩u₂) / ||...||<br>
        ...<br>
        <br>
    Examples:<br>
        &gt;&gt;&gt; v1 = np.array([1., 1., 0.])<br>
        &gt;&gt;&gt; v2 = np.array([1., 0., 0.])<br>
        &gt;&gt;&gt; Q = gram_schmidt(v1, v2)<br>
        &gt;&gt;&gt; np.allclose(Q.T @ Q, np.eye(2))  # Ортонормированность<br>
        True<br>
    &quot;&quot;&quot;<br>
    if len(vectors) == 0:<br>
        raise ValueError(&quot;Необходимо передать хотя бы один вектор&quot;)<br>
    <br>
    # Порог по умолчанию<br>
    if tol is None:<br>
        tol = 10 * numpy.finfo(float).eps<br>
    <br>
    # Преобразуем векторы в массивы-столбцы<br>
    vectors_list = []<br>
    n = None<br>
    for v in vectors:<br>
        v_arr = numpy.asarray(v).flatten()<br>
        if n is None:<br>
            n = len(v_arr)<br>
        elif len(v_arr) != n:<br>
            raise ValueError(f&quot;Все векторы должны иметь одинаковую размерность, получены {n} и {len(v_arr)}&quot;)<br>
        vectors_list.append(v_arr)<br>
    <br>
    # Ортогонализация<br>
    orthonormal_basis = []<br>
    <br>
    for v in vectors_list:<br>
        # Начинаем с исходного вектора<br>
        u = v.copy()<br>
        <br>
        # Вычитаем проекции на все предыдущие ортонормированные векторы<br>
        for q in orthonormal_basis:<br>
            # Проекция: proj_q(u) = ⟨u, q⟩ q<br>
            # Для комплексных: используем vdot (сопряжённое скалярное произведение)<br>
            projection_coef = numpy.vdot(q, u)<br>
            u = u - projection_coef * q<br>
        <br>
        # Нормализуем<br>
        norm = numpy.linalg.norm(u)<br>
        <br>
        # Если вектор стал нулевым (линейно зависим от предыдущих), пропускаем<br>
        if norm &gt; tol:<br>
            u_normalized = u / norm<br>
            orthonormal_basis.append(u_normalized)<br>
    <br>
    # Если нет независимых векторов<br>
    if len(orthonormal_basis) == 0:<br>
        return numpy.empty((n, 0), dtype=vectors_list[0].dtype)<br>
    <br>
    # Собираем в матрицу (векторы = столбцы)<br>
    Q = numpy.column_stack(orthonormal_basis)<br>
    <br>
    return Q<br>
<br>
<br>
def orthogonalize_svd(*vectors, tol=None):<br>
    &quot;&quot;&quot;Ортогонализует набор векторов через SVD разложение.<br>
    <br>
    Строит ортонормированный базис подпространства, натянутого на входные векторы,<br>
    используя сингулярное разложение (SVD). Численно более стабильный метод,<br>
    чем классический Грам-Шмидт.<br>
    <br>
    Args:<br>
        *vectors: Набор векторов для ортогонализации.<br>
                  Каждый вектор размера (n,) или (n, 1).<br>
        tol: Относительный порог для определения линейной зависимости.<br>
             По умолчанию: max(размеры) * машинная_точность<br>
        <br>
    Returns:<br>
        Массив формы (n, k), где k ≤ len(vectors) - количество линейно независимых векторов.<br>
        Столбцы образуют ортонормированный базис span(vectors).<br>
        Если все векторы нулевые или линейно зависимые от нуля, возвращает массив формы (n, 0).<br>
        <br>
    Notes:<br>
        - Использует SVD для численной устойчивости<br>
        - Порядок векторов НЕ влияет на базис (в отличие от Грама-Шмидта)<br>
        - SVD выбирает &quot;наилучший&quot; базис (главные направления)<br>
        - Векторы базиса ортонормированы: Q.T @ Q = I<br>
        - Для получения проектора: P = Q @ Q.T<br>
        - Более медленный, но более точный чем Грам-Шмидт<br>
        <br>
    Examples:<br>
        &gt;&gt;&gt; v1 = np.array([3., 4., 0.])<br>
        &gt;&gt;&gt; v2 = np.array([1., 0., 1.])<br>
        &gt;&gt;&gt; Q = orthogonalize_svd(v1, v2)<br>
        &gt;&gt;&gt; Q.shape  # (3, 2)<br>
        &gt;&gt;&gt; np.allclose(Q.T @ Q, np.eye(2))  # Ортонормированность<br>
        True<br>
        <br>
        &gt;&gt;&gt; # Линейно зависимые векторы<br>
        &gt;&gt;&gt; v1 = np.array([1., 0., 0.])<br>
        &gt;&gt;&gt; v2 = np.array([2., 0., 0.])  # v2 = 2*v1<br>
        &gt;&gt;&gt; Q = orthogonalize_svd(v1, v2)<br>
        &gt;&gt;&gt; Q.shape  # (3, 1) - только один независимый вектор<br>
    &quot;&quot;&quot;<br>
    if len(vectors) == 0:<br>
        raise ValueError(&quot;Необходимо передать хотя бы один вектор&quot;)<br>
    <br>
    # Преобразуем векторы в массив (векторы = строки)<br>
    vectors_array = [numpy.asarray(v).flatten() for v in vectors]<br>
    A = numpy.vstack(vectors_array)<br>
    <br>
    # SVD разложение<br>
    u, s, vh = numpy.linalg.svd(A, full_matrices=True)<br>
    <br>
    # Определяем порог для линейной независимости<br>
    if tol is None:<br>
        tol = max(A.shape) * numpy.finfo(A.dtype).eps<br>
    <br>
    threshold = tol * s[0] if s.size &gt; 0 else tol<br>
    <br>
    # Ранг = количество значимых сингулярных чисел<br>
    rank = numpy.sum(s &gt; threshold)<br>
    <br>
    # Ортонормированный базис = правые сингулярные векторы для ненулевых σ<br>
    # Транспонируем, чтобы векторы были столбцами<br>
    orthonormal_basis = vh[:rank].T.conj()<br>
    <br>
    return orthonormal_basis<br>
<br>
<br>
def orthogonalize(*vectors, method='svd', tol=None):<br>
    &quot;&quot;&quot;Ортогонализует набор векторов одним из двух методов.<br>
    <br>
    Универсальная функция ортогонализации с выбором метода.<br>
    <br>
    Args:<br>
        *vectors: Набор векторов для ортогонализации.<br>
                  Каждый вектор размера (n,) или (n, 1).<br>
        method: Метод ортогонализации:<br>
                - 'svd': SVD разложение (по умолчанию, более стабильный)<br>
                - 'gram_schmidt' или 'gs': классический Грам-Шмидт<br>
        tol: Порог для определения линейной зависимости.<br>
             Интерпретация зависит от метода.<br>
        <br>
    Returns:<br>
        Массив формы (n, k), где k ≤ len(vectors).<br>
        Столбцы образуют ортонормированный базис span(vectors).<br>
        <br>
    Notes:<br>
        - SVD: численно стабильный, базис не зависит от порядка векторов<br>
        - Грам-Шмидт: быстрее, но менее стабильный, порядок векторов важен<br>
        <br>
    Examples:<br>
        &gt;&gt;&gt; v1 = np.array([1., 1., 0.])<br>
        &gt;&gt;&gt; v2 = np.array([1., 0., 0.])<br>
        &gt;&gt;&gt; Q_svd = orthogonalize(v1, v2, method='svd')<br>
        &gt;&gt;&gt; Q_gs = orthogonalize(v1, v2, method='gram_schmidt')<br>
        &gt;&gt;&gt; # Оба ортонормированы, но могут давать разные базисы<br>
    &quot;&quot;&quot;<br>
    if method in ('svd', 'SVD'):<br>
        return orthogonalize_svd(*vectors, tol=tol)<br>
    elif method in ('gram_schmidt', 'gs', 'GS', 'Gram-Schmidt'):<br>
        return gram_schmidt(*vectors, tol=tol)<br>
    else:<br>
        raise ValueError(f&quot;Неизвестный метод: {method}. Используйте 'svd' или 'gram_schmidt'&quot;)<br>
<br>
<br>
def is_projector(P, tol=None):<br>
    &quot;&quot;&quot;Проверяет, является ли матрица ортогональным проектором.<br>
    <br>
    Ортогональный проектор должен удовлетворять двум условиям:<br>
    1. Идемпотентность: P @ P = P<br>
    2. Эрмитовость: P^H = P (для вещественных матриц: P.T = P)<br>
    <br>
    Args:<br>
        P: Матрица для проверки, размер (n, n)<br>
        tol: Порог для численного сравнения.<br>
             По умолчанию: sqrt(n) * машинная_точность * ||P||<br>
        <br>
    Returns:<br>
        True если P - ортогональный проектор, False иначе<br>
        <br>
    Notes:<br>
        - Проверяет обе необходимые характеристики проектора<br>
        - Учитывает численные погрешности через параметр tol<br>
        - Для нулевой матрицы возвращает True (проектор на {0})<br>
        - Дополнительно проверяется, что сингулярные числа ≈ 0 или 1<br>
        <br>
    Examples:<br>
        &gt;&gt;&gt; # Проектор на ось X<br>
        &gt;&gt;&gt; P = vector_projector([1., 0., 0.])<br>
        &gt;&gt;&gt; is_projector(P)<br>
        True<br>
        <br>
        &gt;&gt;&gt; # Обычная матрица (не проектор)<br>
        &gt;&gt;&gt; A = np.array([[1, 2], [3, 4]])<br>
        &gt;&gt;&gt; is_projector(A)<br>
        False<br>
        <br>
        &gt;&gt;&gt; # Проектор на плоскость<br>
        &gt;&gt;&gt; P = subspace_projector([1,0,0], [0,1,0])<br>
        &gt;&gt;&gt; is_projector(P)<br>
        True<br>
    &quot;&quot;&quot;<br>
    P = numpy.asarray(P)<br>
    <br>
    # Проверка квадратности<br>
    if P.ndim != 2 or P.shape[0] != P.shape[1]:<br>
        return False<br>
    <br>
    n = P.shape[0]<br>
    <br>
    # Конвертируем в float для корректной работы с numpy.finfo<br>
    P = _ensure_inexact(P)<br>
    <br>
    # Определяем порог<br>
    if tol is None:<br>
        P_norm = numpy.linalg.norm(P)<br>
        if P_norm == 0:<br>
            return True  # Нулевая матрица - проектор на {0}<br>
        tol = numpy.sqrt(n) * numpy.finfo(P.dtype).eps * P_norm<br>
    <br>
    # 1. Проверка идемпотентности: P @ P = P<br>
    P_squared = P @ P<br>
    idempotent = numpy.allclose(P_squared, P, atol=tol)<br>
    <br>
    if not idempotent:<br>
        return False<br>
    <br>
    # 2. Проверка эрмитовости: P^H = P<br>
    P_hermitian = P.T.conj()<br>
    hermitian = numpy.allclose(P_hermitian, P, atol=tol)<br>
    <br>
    if not hermitian:<br>
        return False<br>
    <br>
    # 3. Дополнительная проверка: сингулярные числа должны быть 0 или 1<br>
    s = numpy.linalg.svd(P, compute_uv=False)<br>
    <br>
    # Более мягкий tolerance для сингулярных чисел<br>
    # (SVD может давать разную точность на разных версиях NumPy/Python)<br>
    svd_tol = max(tol, 10 * numpy.finfo(P.dtype).eps * P_norm)<br>
    <br>
    # Проверяем, что каждое сингулярное число близко либо к 0, либо к 1<br>
    for sigma in s:<br>
        # Расстояние до ближайшего из {0, 1}<br>
        distance_to_binary = min(abs(sigma - 0.0), abs(sigma - 1.0))<br>
        if distance_to_binary &gt; svd_tol:<br>
            return False<br>
    <br>
    return True<br>
<br>
<br>
def projector_basis(P, rtol=None):<br>
    &quot;&quot;&quot;Извлекает ортонормированный базис подпространства из проектора.<br>
    <br>
    Для проектора P на подпространство V возвращает матрицу Q, столбцы которой<br>
    образуют ортонормированный базис V. Обратная операция: P = Q @ Q.T<br>
    <br>
    Args:<br>
        P: Ортогональный проектор на подпространство, размер (n, n)<br>
        rtol: Относительный порог для определения ранга проектора.<br>
              По умолчанию: max(n) * машинная_точность<br>
        <br>
    Returns:<br>
        Матрица размера (n, k) где k = dim(V) = rank(P).<br>
        Столбцы образуют ортонормированный базис подпространства.<br>
        Если P = 0 (тривиальное подпространство), возвращает массив формы (n, 0).<br>
        <br>
    Notes:<br>
        - Использует SVD разложение проектора<br>
        - Базис извлекается из правых сингулярных векторов<br>
        - Векторы ортонормированы: Q.T @ Q = I_k<br>
        - Проверка: P ≈ Q @ Q.T (с точностью до численных ошибок)<br>
        <br>
    Examples:<br>
        &gt;&gt;&gt; # Создаём проектор на плоскость XY<br>
        &gt;&gt;&gt; P = subspace_projector([1,0,0], [0,1,0])<br>
        &gt;&gt;&gt; Q = projector_basis(P)<br>
        &gt;&gt;&gt; Q.shape  # (3, 2)<br>
        &gt;&gt;&gt; np.allclose(P, Q @ Q.T)  # Восстановление проектора<br>
        True<br>
    &quot;&quot;&quot;<br>
    P = numpy.asarray(P)<br>
    <br>
    # SVD разложение проектора<br>
    u, s, vh = numpy.linalg.svd(P, full_matrices=True)<br>
    <br>
    # Определяем порог<br>
    if rtol is None:<br>
        rtol = max(P.shape) * numpy.finfo(P.dtype).eps<br>
    <br>
    threshold = rtol * s[0] if s.size &gt; 0 else rtol<br>
    <br>
    # Ранг = количество значимых сингулярных чисел<br>
    rank = numpy.sum(s &gt; threshold)<br>
    <br>
    if rank == 0:<br>
        # Тривиальное подпространство {0}<br>
        return numpy.empty((P.shape[0], 0), dtype=P.dtype)<br>
    <br>
    # Базис = правые сингулярные векторы для ненулевых σ<br>
    # (транспонируем, чтобы векторы были столбцами)<br>
    basis = vh[:rank].T.conj()<br>
    <br>
    return basis<br>
<br>
<br>
def subspace_intersection(P1, P2, tol=None):<br>
    &quot;&quot;&quot;Возвращает проектор на пересечение двух подпространств.<br>
    <br>
    Вычисляет проектор на V1 ∩ V2, где V1 и V2 заданы проекторами P1 и P2.<br>
    Использует метод через нуль-пространство: V1 ∩ V2 = V1 ∩ ker(I - P2).<br>
    <br>
    Args:<br>
        P1: Проектор на первое подпространство V1, размер (n, n)<br>
        P2: Проектор на второе подпространство V2, размер (n, n)<br>
        tol: Порог для определения линейной зависимости.<br>
             По умолчанию: max(n) * машинная_точность<br>
        <br>
    Returns:<br>
        Матрица проектора на пересечение V1 ∩ V2, размер (n, n)<br>
        <br>
    Notes:<br>
        - Если подпространства не пересекаются (только в 0), возвращает нулевой проектор<br>
        - Метод: находим базис V1, проецируем на V2, ищем векторы, оставшиеся в V1<br>
        - Математически: v ∈ V1 ∩ V2 ⟺ v ∈ V1 и P2 @ v = v<br>
        - dim(V1 ∩ V2) ≤ min(dim(V1), dim(V2))<br>
        - Для ортогональных подпространств: V1 ∩ V2 = {0}<br>
        <br>
    Examples:<br>
        &gt;&gt;&gt; # Плоскость XY и плоскость XZ пересекаются по оси X<br>
        &gt;&gt;&gt; P_xy = subspace_projector([1,0,0], [0,1,0])<br>
        &gt;&gt;&gt; P_xz = subspace_projector([1,0,0], [0,0,1])<br>
        &gt;&gt;&gt; P_x = subspace_intersection(P_xy, P_xz)<br>
        &gt;&gt;&gt; # P_x - проектор на ось X (dim = 1)<br>
        <br>
        &gt;&gt;&gt; # Ортогональные подпространства<br>
        &gt;&gt;&gt; P_x = vector_projector([1,0,0])<br>
        &gt;&gt;&gt; P_y = vector_projector([0,1,0])<br>
        &gt;&gt;&gt; P_int = subspace_intersection(P_x, P_y)<br>
        &gt;&gt;&gt; # P_int ≈ 0 (пересечение пустое)<br>
    &quot;&quot;&quot;<br>
    P1 = numpy.asarray(P1)<br>
    P2 = numpy.asarray(P2)<br>
    <br>
    if P1.shape != P2.shape:<br>
        raise ValueError(f&quot;Проекторы должны иметь одинаковый размер, получены {P1.shape} и {P2.shape}&quot;)<br>
    <br>
    # Извлекаем базис V1 из проектора P1<br>
    basis1 = projector_basis(P1, rtol=tol)<br>
    <br>
    if basis1.size == 0:<br>
        # V1 = {0}, пересечение пустое<br>
        return numpy.zeros_like(P1)<br>
    <br>
    # Проецируем базисные векторы V1 на V2<br>
    # Вектор v ∈ V1 лежит в V1 ∩ V2 ⟺ P2 @ v = v<br>
    projected_basis = P2 @ basis1<br>
    <br>
    # Разность: (P2 @ v - v) должна быть нулевой для векторов из пересечения<br>
    diff = projected_basis - basis1<br>
    <br>
    # Находим нуль-пространство diff (линейные комбинации столбцов basis1,<br>
    # которые не изменяются при проекции на V2)<br>
    # diff @ c ≈ 0  =&gt;  c задаёт вектор из пересечения<br>
    <br>
    # Определяем абсолютный порог для сингулярных чисел<br>
    # Используем норму базиса как характерный масштаб<br>
    if tol is None:<br>
        tol = max(P1.shape) * numpy.finfo(P1.dtype).eps<br>
    <br>
    # Абсолютный порог учитывает масштаб задачи<br>
    threshold = tol * max(1.0, numpy.linalg.norm(basis1))<br>
    <br>
    # Используем существующую функцию с абсолютным порогом<br>
    null_coefs = nullspace_basis(diff, atol=threshold)<br>
    <br>
    if null_coefs.size == 0:<br>
        # Пересечение пустое (только нулевой вектор)<br>
        return numpy.zeros_like(P1)<br>
    <br>
    # Строим базис пересечения: линейные комбинации basis1<br>
    intersection_basis = basis1 @ null_coefs<br>
    <br>
    # Проектор = базис @ базис^H<br>
    return intersection_basis @ intersection_basis.T.conj()<br>
<br>
<br>
def project_onto_affine(x, C, b):<br>
    &quot;&quot;&quot;Возвращает ортогональную проекцию вектора x на аффинное множество, заданное C @ y = b.<br>
    <br>
    Args:<br>
        x: Вектор размера (n,)<br>
        C: Линейно-независимая матрица размера (m, n), задающая линейное отображение<br>
        b: Вектор размера (m,), задающий сдвиг аффинного множества<br>
<br>
    Returns:<br>
        Вектор размера (n,) - проекция x на множество {y | C @ y = b}<br>
    &quot;&quot;&quot;<br>
<br>
    x = numpy.asarray(x).flatten()<br>
    C = numpy.asarray(C)<br>
    b = numpy.asarray(b).flatten()<br>
    <br>
    if C.shape[0] != b.shape[0]:<br>
        raise ValueError(f&quot;Размерность b должна соответствовать числу строк C, получены {C.shape[0]} и {b.shape[0]}&quot;)<br>
    if C.shape[1] != x.shape[0]:<br>
        raise ValueError(f&quot;Размерность x должна соответствовать числу столбцов C, получены {C.shape[1]} и {x.shape[0]}&quot;)<br>
    <br>
    Ct = C.T.conj()<br>
    CCt_inv = numpy.linalg.pinv(C @ Ct)<br>
    projection = x - Ct @ (CCt_inv @ (C @ x - b))<br>
    return projection<br>
<br>
def affine_projector(C, b):<br>
    &quot;&quot;&quot;Возвращает проектор на аффинное множество A, заданное C @ y = b и вектор смещения B:<br>
<br>
    Решение следует подставлять в форму x^ = x - (A.x - B).<br>
    Здесь<br>
    A = C.T @ (C @ C.T)^(-1) @ C<br>
    B = C.T @ (C @ C.T)^(-1) @ b<br>
    &quot;&quot;&quot;<br>
    C = numpy.asarray(C)<br>
    b = numpy.asarray(b).flatten()<br>
    <br>
    if C.shape[0] != b.shape[0]:<br>
        raise ValueError(f&quot;Размерность b должна соответствовать числу строк C, получены {C.shape[0]} и {b.shape[0]}&quot;)<br>
    <br>
    Ct = C.T.conj()<br>
    CCt_inv = numpy.linalg.pinv(C @ Ct)<br>
    <br>
    K = Ct @ CCt_inv<br>
    A = K @ C<br>
    B = K @ b<br>
<br>
    return A, B<br>
<br>
def metric_project_onto_constraints(<br>
        q: numpy.ndarray, <br>
        H: numpy.ndarray,<br>
        M_inv: numpy.ndarray,<br>
        error: numpy.ndarray = None,<br>
        h: numpy.ndarray = None) -&gt; numpy.ndarray:<br>
    &quot;&quot;&quot;Проецировать скорости на ограничения<br>
    <br>
    q - текущий вектор<br>
    H - матрица ограничений<br>
    M_inv - метрическая матрица<br>
    <br>
    Одно из двух должно быть задано:<br>
        error - текущая ошибка<br>
        h - правая часть ограничений<br>
    &quot;&quot;&quot;<br>
    if error is None:<br>
        error = H @ q - h<br>
<br>
    S = H @ M_inv @ H.T<br>
<br>
    lmbda = numpy.linalg.solve(S, error)<br>
    corrected = q - M_inv @ H.T @ lmbda<br>
<br>
    return corrected <br>
<!-- END SCAT CODE -->
</body>
</html>
