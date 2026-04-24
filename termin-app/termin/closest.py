import numpy as np

def _dot(a, b): return float(np.dot(a, b))

def _project_point_to_segment(p, a, b):
    # возвращает (t_clamped, closest_point)
    ab = b - a
    denom = _dot(ab, ab)
    if denom < 1e-12:
        return 0.0, a  # вырожденный отрезок
    t = _dot(p - a, ab) / denom
    t_clamped = max(0.0, min(1.0, t))
    return t_clamped, a + t_clamped * ab

def closest_points_between_segments(p0, p1, q0, q1, eps=1e-12):
    """
    Возвращает (p_near, q_near, dist) — ближайшие точки на отрезках [p0,p1] и [q0,q1] и расстояние.
    Корректно обрабатывает границы и вырожденные случаи.
    """
    u = p1 - p0
    v = q1 - q0
    w0 = p0 - q0

    a = _dot(u, u)
    b = _dot(u, v)
    c = _dot(v, v)
    d = _dot(u, w0)
    e = _dot(v, w0)
    D = a * c - b * b

    candidates = []

    # Алгоритм ищет минимум на квадрате (s,t):([0,1],[0,1])
    # 1) Внутренний кандидат
    if D > eps:
        s = (b * e - c * d) / D
        t = (a * e - b * d) / D
        if 0.0 <= s <= 1.0 and 0.0 <= t <= 1.0:
            p_int = p0 + s * u
            q_int = q0 + t * v
            candidates.append((p_int, q_int))
    # Если прямые параллельны (D<eps), то решений множество и одно из них 
    # лежит на рёбрах, поэтому ничего не делаем

    # 2) Рёбра и углы (фиксируем одну переменную и оптимизируем другую)
    # t = 0  (Q = q0) -> проектируем q0 на P
    s_t0, p_t0 = _project_point_to_segment(q0, p0, p1)
    candidates.append((p_t0, q0))

    # t = 1  (Q = q1) -> проектируем q1 на P
    s_t1, p_t1 = _project_point_to_segment(q1, p0, p1)
    candidates.append((p_t1, q1))

    # s = 0  (P = p0) -> проектируем p0 на Q
    t_s0, q_s0 = _project_point_to_segment(p0, q0, q1)
    candidates.append((p0, q_s0))

    # s = 1  (P = p1) -> проектируем p1 на Q
    t_s1, q_s1 = _project_point_to_segment(p1, q0, q1)
    candidates.append((p1, q_s1))

    # 3) Выбор лучшего кандидата
    best = None
    best_d2 = float("inf")
    for P, Q in candidates:
        d2 = _dot(P - Q, P - Q)
        if d2 < best_d2:
            best_d2 = d2
            best = (P, Q)

    p_near, q_near = best
    return p_near, q_near, float(np.sqrt(best_d2))

def closest_points_between_capsules(p0, p1, r1, q0, q1, r2):
    """
    Возвращает ближайшие точки на поверхностях двух капсул и расстояние между ними.
    Капсулы заданы своими осями (отрезками [p0,p1] и [q0,q1]) и радиусами r1, r2.
    """

    # Используем уже реализованный поиск ближайших точек между отрезками
    p, q, dist_axis = closest_points_between_segments(p0, p1, q0, q1)

    # Если оси почти совпадают (вектор нулевой)
    diff = p - q
    dist = np.linalg.norm(diff)

    # Если оси пересекаются или капсулы перекрываются
    penetration = r1 + r2 - dist

    if penetration >= 0.0:
        # Пересекаются
        # Поскольку множество точек имеют расстояние 0.0 до коллайдера-антагонистa.
        # Выбор решения осуществляется из соображения наибольшей плавности.
        k = r1 / (r1 + r2) if (r1 + r2) > 1e-12 else 0.5
        p_surface = p - diff * k
        q_surface = q + diff * (1 - k)
        distance = 0.0
    else:
        # Разделены
        direction = diff / dist
        p_surface = p - direction * r1
        q_surface = q + direction * r2
        distance = dist - (r1 + r2)

    return p_surface, q_surface, distance

def closest_points_between_capsule_and_sphere(capsule_a, capsule_b, capsule_r, sphere_center, sphere_r):
    """
    Возвращает ближайшие точки на поверхности капсулы и сферы, а также расстояние между ними.
    Капсула задана своими концами (отрезком [capsule_a, capsule_b]) и радиусом capsule_r.
    Сфера задана центром sphere_center и радиусом sphere_r.
    """

    # Используем уже реализованный поиск ближайших точек между отрезком и точкой
    t, p = _project_point_to_segment(sphere_center, capsule_a, capsule_b)

    diff = p - sphere_center
    dist = np.linalg.norm(diff)

    penetration = capsule_r + sphere_r - dist

    if penetration >= 0.0:
        # Пересекаются
        k = capsule_r / (capsule_r + sphere_r) if (capsule_r + sphere_r) > 1e-12 else 0.5
        p_surface = p - diff * k
        q_surface = sphere_center + diff * (1 - k)
        distance = 0.0
    else:
        # Разделены
        direction = diff / dist
        p_surface = p - direction * capsule_r
        q_surface = sphere_center + direction * sphere_r
        distance = dist - (capsule_r + sphere_r)

    return p_surface, q_surface, max(0.0, distance)