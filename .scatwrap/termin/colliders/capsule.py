<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/capsule.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
from termin.closest import closest_points_between_segments, closest_points_between_capsules, closest_points_between_capsule_and_sphere<br>
import numpy<br>
from termin.colliders.collider import Collider<br>
from termin.colliders.sphere import SphereCollider<br>
<br>
class CapsuleCollider(Collider):<br>
&#9;def closest_to_ray(self, ray: &quot;Ray3&quot;):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Ближайшие точки между сегментом капсулы и лучом:<br>
&#9;&#9;Реализуем прямой рейкаст в капсулу (цилиндр вдоль [a,b] + две сферы)<br>
&#9;&#9;через аналитические уравнения:<br>
&#9;&#9;&#9;|(w_perp + t * D_perp)|^2 = r^2  — пересечение с цилиндром<br>
&#9;&#9;&#9;|O + tD - C|^2 = r^2              — пересечение с каждой сферой<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;from termin.closest import closest_points_between_segments<br>
<br>
&#9;&#9;O = ray.origin<br>
&#9;&#9;D = ray.direction<br>
&#9;&#9;A = self.a<br>
&#9;&#9;B = self.b<br>
&#9;&#9;r = self.radius<br>
<br>
&#9;&#9;axis = B - A<br>
&#9;&#9;length = numpy.linalg.norm(axis)<br>
&#9;&#9;if length &lt; 1e-8:<br>
&#9;&#9;&#9;# Вырожденная капсула → сфера.<br>
&#9;&#9;&#9;return SphereCollider(A, r).closest_to_ray(ray)<br>
<br>
&#9;&#9;U = axis / length<br>
<br>
&#9;&#9;# Проверяем, стартует ли луч внутри капсулы.<br>
&#9;&#9;proj0 = numpy.dot(O - A, U)<br>
&#9;&#9;closest_axis_pt = A + numpy.clip(proj0, 0.0, length) * U<br>
&#9;&#9;dist_axis0 = numpy.linalg.norm(O - closest_axis_pt)<br>
&#9;&#9;if dist_axis0 &lt;= r + 1e-8:<br>
&#9;&#9;&#9;return O, O, 0.0<br>
<br>
&#9;&#9;def sphere_hit(center: numpy.ndarray) -&gt; float | None:<br>
&#9;&#9;&#9;m = O - center<br>
&#9;&#9;&#9;b = numpy.dot(m, D)<br>
&#9;&#9;&#9;c = numpy.dot(m, m) - r * r<br>
&#9;&#9;&#9;disc = b * b - c<br>
&#9;&#9;&#9;if disc &lt; 0:<br>
&#9;&#9;&#9;&#9;return None<br>
&#9;&#9;&#9;sqrt_disc = numpy.sqrt(disc)<br>
&#9;&#9;&#9;t0 = -b - sqrt_disc<br>
&#9;&#9;&#9;if t0 &gt;= 0:<br>
&#9;&#9;&#9;&#9;return t0<br>
&#9;&#9;&#9;t1 = -b + sqrt_disc<br>
&#9;&#9;&#9;return t1 if t1 &gt;= 0 else None<br>
<br>
&#9;&#9;t_candidates = []<br>
<br>
&#9;&#9;# Пересечение с цилиндрической частью: |w_perp + t D_perp|^2 = r^2<br>
&#9;&#9;w = O - A<br>
&#9;&#9;w_par = numpy.dot(w, U)<br>
&#9;&#9;w_perp = w - w_par * U<br>
&#9;&#9;D_par = numpy.dot(D, U)<br>
&#9;&#9;D_perp = D - D_par * U<br>
<br>
&#9;&#9;a = numpy.dot(D_perp, D_perp)<br>
&#9;&#9;b = 2.0 * numpy.dot(D_perp, w_perp)<br>
&#9;&#9;c = numpy.dot(w_perp, w_perp) - r * r<br>
<br>
&#9;&#9;if a &gt; 1e-12:<br>
&#9;&#9;&#9;disc = b * b - 4.0 * a * c<br>
&#9;&#9;&#9;if disc &gt;= 0.0:<br>
&#9;&#9;&#9;&#9;sqrt_disc = numpy.sqrt(disc)<br>
&#9;&#9;&#9;&#9;t0 = (-b - sqrt_disc) / (2.0 * a)<br>
&#9;&#9;&#9;&#9;t1 = (-b + sqrt_disc) / (2.0 * a)<br>
&#9;&#9;&#9;&#9;for t in (t0, t1):<br>
&#9;&#9;&#9;&#9;&#9;if t &lt; 0:<br>
&#9;&#9;&#9;&#9;&#9;&#9;continue<br>
&#9;&#9;&#9;&#9;&#9;s = w_par + t * D_par  # параметр вдоль оси капсулы<br>
&#9;&#9;&#9;&#9;&#9;if 0.0 &lt;= s &lt;= length:<br>
&#9;&#9;&#9;&#9;&#9;&#9;t_candidates.append(t)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;# Луч параллелен оси. Если проекция в пределах радиуса, стукнемся об крышки.<br>
&#9;&#9;&#9;if c &lt;= 0.0 and (D_par &gt; 0.0 or D_par &lt; 0.0):<br>
&#9;&#9;&#9;&#9;# Попадание в цилиндрическую часть, но точное t определят сферы.<br>
&#9;&#9;&#9;&#9;pass<br>
<br>
&#9;&#9;# Пересечения с капами<br>
&#9;&#9;t_sphere_a = sphere_hit(A)<br>
&#9;&#9;if t_sphere_a is not None:<br>
&#9;&#9;&#9;t_candidates.append(t_sphere_a)<br>
&#9;&#9;t_sphere_b = sphere_hit(B)<br>
&#9;&#9;if t_sphere_b is not None:<br>
&#9;&#9;&#9;t_candidates.append(t_sphere_b)<br>
<br>
&#9;&#9;if t_candidates:<br>
&#9;&#9;&#9;t_hit = min(t_candidates)<br>
&#9;&#9;&#9;p_hit = ray.point_at(t_hit)<br>
&#9;&#9;&#9;return p_hit, p_hit, 0.0<br>
<br>
&#9;&#9;# Нет пересечения — берем ближайшие точки между лучом (обрезанным) и осью капсулы.<br>
&#9;&#9;FAR = 1e6<br>
&#9;&#9;p_seg, p_ray, dist_axis = closest_points_between_segments(<br>
&#9;&#9;&#9;A, B,<br>
&#9;&#9;&#9;O, O + D * FAR<br>
&#9;&#9;)<br>
&#9;&#9;dir_vec = p_ray - p_seg<br>
&#9;&#9;n = numpy.linalg.norm(dir_vec)<br>
&#9;&#9;if n &gt; 1e-8:<br>
&#9;&#9;&#9;p_col = p_seg + dir_vec * (r / n)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;# Луч параллелен оси: сдвигаем вдоль любой нормали.<br>
&#9;&#9;&#9;normal = numpy.cross(U, numpy.array([1.0, 0.0, 0.0]))<br>
&#9;&#9;&#9;if numpy.linalg.norm(normal) &lt; 1e-8:<br>
&#9;&#9;&#9;&#9;normal = numpy.cross(U, numpy.array([0.0, 1.0, 0.0]))<br>
&#9;&#9;&#9;normal = normal / numpy.linalg.norm(normal)<br>
&#9;&#9;&#9;p_col = p_seg + normal * r<br>
&#9;&#9;return p_col, p_ray, numpy.linalg.norm(p_col - p_ray)<br>
&#9;<br>
&#9;def __init__(self, a: numpy.ndarray, b: numpy.ndarray, radius: float):<br>
&#9;&#9;self.a = a<br>
&#9;&#9;self.b = b<br>
&#9;&#9;self.radius = radius<br>
<br>
&#9;def transform_by(self, transform: 'Pose3'):<br>
&#9;&#9;&quot;&quot;&quot;Return a new CapsuleCollider transformed by the given Pose3.&quot;&quot;&quot;<br>
&#9;&#9;new_a = transform.transform_point(self.a)<br>
&#9;&#9;new_b = transform.transform_point(self.b)<br>
&#9;&#9;return CapsuleCollider(new_a, new_b, self.radius)<br>
&#9;<br>
&#9;def closest_to_capsule(self, other: &quot;CapsuleCollider&quot;):<br>
&#9;&#9;&quot;&quot;&quot;Return the closest points and distance between this capsule and another capsule.&quot;&quot;&quot;<br>
&#9;&#9;p_near, q_near, dist = closest_points_between_capsules(<br>
&#9;&#9;&#9;self.a, self.b, self.radius,<br>
&#9;&#9;&#9;other.a, other.b, other.radius)<br>
&#9;&#9;return p_near, q_near, dist<br>
<br>
&#9;def closest_to_sphere(self, other: &quot;SphereCollider&quot;):<br>
&#9;&#9;&quot;&quot;&quot;Return the closest points and distance between this capsule and a sphere.&quot;&quot;&quot;<br>
&#9;&#9;p_near, q_near, dist = closest_points_between_capsule_and_sphere(<br>
&#9;&#9;&#9;self.a, self.b, self.radius,<br>
&#9;&#9;&#9;other.center, other.radius)<br>
&#9;&#9;return p_near, q_near, dist<br>
<br>
&#9;def closest_to_union_collider(self, other: &quot;UnionCollider&quot;):<br>
&#9;&#9;&quot;&quot;&quot;Return the closest points and distance between this capsule and a union collider.&quot;&quot;&quot;<br>
&#9;&#9;a,b,c = other.closest_to_collider(self)<br>
&#9;&#9;return b,a,c<br>
<br>
&#9;def closest_to_collider(self, other: &quot;Collider&quot;):<br>
&#9;&#9;&quot;&quot;&quot;Return the closest points and distance between this collider and another collider.&quot;&quot;&quot;<br>
<br>
&#9;&#9;from .sphere import SphereCollider<br>
&#9;&#9;from .union_collider import UnionCollider<br>
<br>
&#9;&#9;if isinstance(other, CapsuleCollider):<br>
&#9;&#9;&#9;return self.closest_to_capsule(other)<br>
&#9;&#9;elif isinstance(other, SphereCollider):<br>
&#9;&#9;&#9;return other.closest_to_sphere(self)<br>
&#9;&#9;elif isinstance(other, UnionCollider):<br>
&#9;&#9;&#9;return self.closest_to_union_collider(other)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;raise NotImplementedError(f&quot;closest_to_collider not implemented for {type(other)}&quot;)<br>
<br>
&#9;def distance(self, other: &quot;Collider&quot;) -&gt; float:<br>
&#9;&#9;&quot;&quot;&quot;Return the distance between this collider and another collider.&quot;&quot;&quot;<br>
&#9;&#9;_, _, dist = self.closest_to_collider(other)<br>
&#9;&#9;return dist<br>
<!-- END SCAT CODE -->
</body>
</html>
