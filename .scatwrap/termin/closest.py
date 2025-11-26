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
&#9;# возвращает (t_clamped, closest_point)<br>
&#9;ab = b - a<br>
&#9;denom = _dot(ab, ab)<br>
&#9;if denom &lt; 1e-12:<br>
&#9;&#9;return 0.0, a  # вырожденный отрезок<br>
&#9;t = _dot(p - a, ab) / denom<br>
&#9;t_clamped = max(0.0, min(1.0, t))<br>
&#9;return t_clamped, a + t_clamped * ab<br>
<br>
def closest_points_between_segments(p0, p1, q0, q1, eps=1e-12):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Возвращает (p_near, q_near, dist) — ближайшие точки на отрезках [p0,p1] и [q0,q1] и расстояние.<br>
&#9;Корректно обрабатывает границы и вырожденные случаи.<br>
&#9;&quot;&quot;&quot;<br>
&#9;u = p1 - p0<br>
&#9;v = q1 - q0<br>
&#9;w0 = p0 - q0<br>
<br>
&#9;a = _dot(u, u)<br>
&#9;b = _dot(u, v)<br>
&#9;c = _dot(v, v)<br>
&#9;d = _dot(u, w0)<br>
&#9;e = _dot(v, w0)<br>
&#9;D = a * c - b * b<br>
<br>
&#9;candidates = []<br>
<br>
&#9;# Алгоритм ищет минимум на квадрате (s,t):([0,1],[0,1])<br>
&#9;# 1) Внутренний кандидат<br>
&#9;if D &gt; eps:<br>
&#9;&#9;s = (b * e - c * d) / D<br>
&#9;&#9;t = (a * e - b * d) / D<br>
&#9;&#9;if 0.0 &lt;= s &lt;= 1.0 and 0.0 &lt;= t &lt;= 1.0:<br>
&#9;&#9;&#9;p_int = p0 + s * u<br>
&#9;&#9;&#9;q_int = q0 + t * v<br>
&#9;&#9;&#9;candidates.append((p_int, q_int))<br>
&#9;# Если прямые параллельны (D&lt;eps), то решений множество и одно из них <br>
&#9;# лежит на рёбрах, поэтому ничего не делаем<br>
<br>
&#9;# 2) Рёбра и углы (фиксируем одну переменную и оптимизируем другую)<br>
&#9;# t = 0  (Q = q0) -&gt; проектируем q0 на P<br>
&#9;s_t0, p_t0 = _project_point_to_segment(q0, p0, p1)<br>
&#9;candidates.append((p_t0, q0))<br>
<br>
&#9;# t = 1  (Q = q1) -&gt; проектируем q1 на P<br>
&#9;s_t1, p_t1 = _project_point_to_segment(q1, p0, p1)<br>
&#9;candidates.append((p_t1, q1))<br>
<br>
&#9;# s = 0  (P = p0) -&gt; проектируем p0 на Q<br>
&#9;t_s0, q_s0 = _project_point_to_segment(p0, q0, q1)<br>
&#9;candidates.append((p0, q_s0))<br>
<br>
&#9;# s = 1  (P = p1) -&gt; проектируем p1 на Q<br>
&#9;t_s1, q_s1 = _project_point_to_segment(p1, q0, q1)<br>
&#9;candidates.append((p1, q_s1))<br>
<br>
&#9;# 3) Выбор лучшего кандидата<br>
&#9;best = None<br>
&#9;best_d2 = float(&quot;inf&quot;)<br>
&#9;for P, Q in candidates:<br>
&#9;&#9;d2 = _dot(P - Q, P - Q)<br>
&#9;&#9;if d2 &lt; best_d2:<br>
&#9;&#9;&#9;best_d2 = d2<br>
&#9;&#9;&#9;best = (P, Q)<br>
<br>
&#9;p_near, q_near = best<br>
&#9;return p_near, q_near, float(np.sqrt(best_d2))<br>
<br>
def closest_points_between_capsules(p0, p1, r1, q0, q1, r2):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Возвращает ближайшие точки на поверхностях двух капсул и расстояние между ними.<br>
&#9;Капсулы заданы своими осями (отрезками [p0,p1] и [q0,q1]) и радиусами r1, r2.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;# Используем уже реализованный поиск ближайших точек между отрезками<br>
&#9;p, q, dist_axis = closest_points_between_segments(p0, p1, q0, q1)<br>
<br>
&#9;# Если оси почти совпадают (вектор нулевой)<br>
&#9;diff = p - q<br>
&#9;dist = np.linalg.norm(diff)<br>
<br>
&#9;# Если оси пересекаются или капсулы перекрываются<br>
&#9;penetration = r1 + r2 - dist<br>
<br>
&#9;if penetration &gt;= 0.0:<br>
&#9;&#9;# Пересекаются<br>
&#9;&#9;# Поскольку множество точек имеют расстояние 0.0 до коллайдера-антагонистa.<br>
&#9;&#9;# Выбор решения осуществляется из соображения наибольшей плавности.<br>
&#9;&#9;k = r1 / (r1 + r2) if (r1 + r2) &gt; 1e-12 else 0.5<br>
&#9;&#9;p_surface = p - diff * k<br>
&#9;&#9;q_surface = q + diff * (1 - k)<br>
&#9;&#9;distance = 0.0<br>
&#9;else:<br>
&#9;&#9;# Разделены<br>
&#9;&#9;direction = diff / dist<br>
&#9;&#9;p_surface = p - direction * r1<br>
&#9;&#9;q_surface = q + direction * r2<br>
&#9;&#9;distance = dist - (r1 + r2)<br>
<br>
&#9;return p_surface, q_surface, distance<br>
<br>
def closest_points_between_capsule_and_sphere(capsule_a, capsule_b, capsule_r, sphere_center, sphere_r):<br>
&#9;&quot;&quot;&quot;<br>
&#9;Возвращает ближайшие точки на поверхности капсулы и сферы, а также расстояние между ними.<br>
&#9;Капсула задана своими концами (отрезком [capsule_a, capsule_b]) и радиусом capsule_r.<br>
&#9;Сфера задана центром sphere_center и радиусом sphere_r.<br>
&#9;&quot;&quot;&quot;<br>
<br>
&#9;# Используем уже реализованный поиск ближайших точек между отрезком и точкой<br>
&#9;t, p = _project_point_to_segment(sphere_center, capsule_a, capsule_b)<br>
<br>
&#9;diff = p - sphere_center<br>
&#9;dist = np.linalg.norm(diff)<br>
<br>
&#9;penetration = capsule_r + sphere_r - dist<br>
<br>
&#9;if penetration &gt;= 0.0:<br>
&#9;&#9;# Пересекаются<br>
&#9;&#9;k = capsule_r / (capsule_r + sphere_r) if (capsule_r + sphere_r) &gt; 1e-12 else 0.5<br>
&#9;&#9;p_surface = p - diff * k<br>
&#9;&#9;q_surface = sphere_center + diff * (1 - k)<br>
&#9;&#9;distance = 0.0<br>
&#9;else:<br>
&#9;&#9;# Разделены<br>
&#9;&#9;direction = diff / dist<br>
&#9;&#9;p_surface = p - direction * capsule_r<br>
&#9;&#9;q_surface = sphere_center + direction * sphere_r<br>
&#9;&#9;distance = dist - (capsule_r + sphere_r)<br>
<br>
&#9;return p_surface, q_surface, max(0.0, distance)<br>
<!-- END SCAT CODE -->
</body>
</html>
