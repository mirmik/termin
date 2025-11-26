<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/closest.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
import numpy as np<br>
<br>
def _dot(a, b): return float(np.dot(a, b))<br>
<br>
def _project_point_to_segment(p, a, b):<br>
    # возвращает (t_clamped, closest_point)<br>
    ab = b - a<br>
    denom = _dot(ab, ab)<br>
    if denom &lt; 1e-12:<br>
        return 0.0, a  # вырожденный отрезок<br>
    t = _dot(p - a, ab) / denom<br>
    t_clamped = max(0.0, min(1.0, t))<br>
    return t_clamped, a + t_clamped * ab<br>
<br>
def closest_points_between_segments(p0, p1, q0, q1, eps=1e-12):<br>
    &quot;&quot;&quot;<br>
    Возвращает (p_near, q_near, dist) — ближайшие точки на отрезках [p0,p1] и [q0,q1] и расстояние.<br>
    Корректно обрабатывает границы и вырожденные случаи.<br>
    &quot;&quot;&quot;<br>
    u = p1 - p0<br>
    v = q1 - q0<br>
    w0 = p0 - q0<br>
<br>
    a = _dot(u, u)<br>
    b = _dot(u, v)<br>
    c = _dot(v, v)<br>
    d = _dot(u, w0)<br>
    e = _dot(v, w0)<br>
    D = a * c - b * b<br>
<br>
    candidates = []<br>
<br>
    # Алгоритм ищет минимум на квадрате (s,t):([0,1],[0,1])<br>
    # 1) Внутренний кандидат<br>
    if D &gt; eps:<br>
        s = (b * e - c * d) / D<br>
        t = (a * e - b * d) / D<br>
        if 0.0 &lt;= s &lt;= 1.0 and 0.0 &lt;= t &lt;= 1.0:<br>
            p_int = p0 + s * u<br>
            q_int = q0 + t * v<br>
            candidates.append((p_int, q_int))<br>
    # Если прямые параллельны (D&lt;eps), то решений множество и одно из них <br>
    # лежит на рёбрах, поэтому ничего не делаем<br>
<br>
    # 2) Рёбра и углы (фиксируем одну переменную и оптимизируем другую)<br>
    # t = 0  (Q = q0) -&gt; проектируем q0 на P<br>
    s_t0, p_t0 = _project_point_to_segment(q0, p0, p1)<br>
    candidates.append((p_t0, q0))<br>
<br>
    # t = 1  (Q = q1) -&gt; проектируем q1 на P<br>
    s_t1, p_t1 = _project_point_to_segment(q1, p0, p1)<br>
    candidates.append((p_t1, q1))<br>
<br>
    # s = 0  (P = p0) -&gt; проектируем p0 на Q<br>
    t_s0, q_s0 = _project_point_to_segment(p0, q0, q1)<br>
    candidates.append((p0, q_s0))<br>
<br>
    # s = 1  (P = p1) -&gt; проектируем p1 на Q<br>
    t_s1, q_s1 = _project_point_to_segment(p1, q0, q1)<br>
    candidates.append((p1, q_s1))<br>
<br>
    # 3) Выбор лучшего кандидата<br>
    best = None<br>
    best_d2 = float(&quot;inf&quot;)<br>
    for P, Q in candidates:<br>
        d2 = _dot(P - Q, P - Q)<br>
        if d2 &lt; best_d2:<br>
            best_d2 = d2<br>
            best = (P, Q)<br>
<br>
    p_near, q_near = best<br>
    return p_near, q_near, float(np.sqrt(best_d2))<br>
<br>
def closest_points_between_capsules(p0, p1, r1, q0, q1, r2):<br>
    &quot;&quot;&quot;<br>
    Возвращает ближайшие точки на поверхностях двух капсул и расстояние между ними.<br>
    Капсулы заданы своими осями (отрезками [p0,p1] и [q0,q1]) и радиусами r1, r2.<br>
    &quot;&quot;&quot;<br>
<br>
    # Используем уже реализованный поиск ближайших точек между отрезками<br>
    p, q, dist_axis = closest_points_between_segments(p0, p1, q0, q1)<br>
<br>
    # Если оси почти совпадают (вектор нулевой)<br>
    diff = p - q<br>
    dist = np.linalg.norm(diff)<br>
<br>
    # Если оси пересекаются или капсулы перекрываются<br>
    penetration = r1 + r2 - dist<br>
<br>
    if penetration &gt;= 0.0:<br>
        # Пересекаются<br>
        # Поскольку множество точек имеют расстояние 0.0 до коллайдера-антагонистa.<br>
        # Выбор решения осуществляется из соображения наибольшей плавности.<br>
        k = r1 / (r1 + r2) if (r1 + r2) &gt; 1e-12 else 0.5<br>
        p_surface = p - diff * k<br>
        q_surface = q + diff * (1 - k)<br>
        distance = 0.0<br>
    else:<br>
        # Разделены<br>
        direction = diff / dist<br>
        p_surface = p - direction * r1<br>
        q_surface = q + direction * r2<br>
        distance = dist - (r1 + r2)<br>
<br>
    return p_surface, q_surface, distance<br>
<br>
def closest_points_between_capsule_and_sphere(capsule_a, capsule_b, capsule_r, sphere_center, sphere_r):<br>
    &quot;&quot;&quot;<br>
    Возвращает ближайшие точки на поверхности капсулы и сферы, а также расстояние между ними.<br>
    Капсула задана своими концами (отрезком [capsule_a, capsule_b]) и радиусом capsule_r.<br>
    Сфера задана центром sphere_center и радиусом sphere_r.<br>
    &quot;&quot;&quot;<br>
<br>
    # Используем уже реализованный поиск ближайших точек между отрезком и точкой<br>
    t, p = _project_point_to_segment(sphere_center, capsule_a, capsule_b)<br>
<br>
    diff = p - sphere_center<br>
    dist = np.linalg.norm(diff)<br>
<br>
    penetration = capsule_r + sphere_r - dist<br>
<br>
    if penetration &gt;= 0.0:<br>
        # Пересекаются<br>
        k = capsule_r / (capsule_r + sphere_r) if (capsule_r + sphere_r) &gt; 1e-12 else 0.5<br>
        p_surface = p - diff * k<br>
        q_surface = sphere_center + diff * (1 - k)<br>
        distance = 0.0<br>
    else:<br>
        # Разделены<br>
        direction = diff / dist<br>
        p_surface = p - direction * capsule_r<br>
        q_surface = sphere_center + direction * sphere_r<br>
        distance = dist - (capsule_r + sphere_r)<br>
<br>
    return p_surface, q_surface, max(0.0, distance)<br>
<!-- END SCAT CODE -->
</body>
</html>
