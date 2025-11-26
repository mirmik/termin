<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/sphere.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
<br>
from termin.closest import closest_points_between_segments, closest_points_between_capsules, closest_points_between_capsule_and_sphere<br>
import numpy<br>
from termin.colliders.collider import Collider<br>
from termin.geombase import Pose3<br>
<br>
<br>
<br>
class SphereCollider(Collider):<br>
&#9;def closest_to_ray(self, ray: &quot;Ray3&quot;):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Аналитическое пересечение луча со сферой.<br>
&#9;&#9;Луч: O + D * t<br>
&#9;&#9;Центр: C<br>
&#9;&#9;Радиус: r<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;O = ray.origin<br>
&#9;&#9;D = ray.direction<br>
&#9;&#9;C = self.center<br>
&#9;&#9;r = self.radius<br>
<br>
&#9;&#9;OC = O - C<br>
&#9;&#9;b = 2 * numpy.dot(D, OC)<br>
&#9;&#9;c = numpy.dot(OC, OC) - r * r<br>
&#9;&#9;disc = b * b - 4 * c<br>
<br>
&#9;&#9;# Нет пересечения — вернуть ближайшие точки<br>
&#9;&#9;if disc &lt; 0:<br>
&#9;&#9;&#9;# t = -dot(OC, D)<br>
&#9;&#9;&#9;#t = -numpy.dot(OC, D)<br>
&#9;&#9;&#9;t = numpy.dot((C - O), D)<br>
&#9;&#9;&#9;if t &lt; 0:<br>
&#9;&#9;&#9;&#9;t = 0<br>
&#9;&#9;&#9;p_ray = ray.point_at(t)<br>
<br>
&#9;&#9;&#9;dir_vec = p_ray - C<br>
&#9;&#9;&#9;dist = numpy.linalg.norm(dir_vec)<br>
&#9;&#9;&#9;if dist &gt; 1e-8:<br>
&#9;&#9;&#9;&#9;p_col = C + dir_vec * (r / dist)<br>
&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;p_col = C + numpy.array([r, 0, 0], dtype=numpy.float32)  # произвольное направление<br>
<br>
&#9;&#9;&#9;return p_col, p_ray, numpy.linalg.norm(p_col - p_ray)<br>
<br>
&#9;&#9;# Есть пересечения: берем ближайшее t &gt;= 0<br>
&#9;&#9;sqrt_disc = numpy.sqrt(disc)<br>
&#9;&#9;t1 = (-b - sqrt_disc) * 0.5<br>
&#9;&#9;t2 = (-b + sqrt_disc) * 0.5<br>
<br>
&#9;&#9;t_hit = None<br>
&#9;&#9;if t1 &gt;= 0:<br>
&#9;&#9;&#9;t_hit = t1<br>
&#9;&#9;elif t2 &gt;= 0:<br>
&#9;&#9;&#9;t_hit = t2<br>
<br>
&#9;&#9;# Пересечение позади луча — перейти к ближайшей точке<br>
&#9;&#9;if t_hit is None:<br>
&#9;&#9;&#9;t = -numpy.dot(OC, D)<br>
&#9;&#9;&#9;if t &lt; 0:<br>
&#9;&#9;&#9;&#9;t = 0<br>
&#9;&#9;&#9;p_ray = ray.point_at(t)<br>
&#9;&#9;&#9;dir_vec = p_ray - C<br>
&#9;&#9;&#9;dist = numpy.linalg.norm(dir_vec)<br>
&#9;&#9;&#9;p_col = C + dir_vec * (r / dist)<br>
&#9;&#9;&#9;return p_col, p_ray, numpy.linalg.norm(p_col - p_ray)<br>
<br>
&#9;&#9;# Корректное пересечение<br>
&#9;&#9;p_ray = ray.point_at(t_hit)<br>
&#9;&#9;dir_vec = p_ray - C<br>
&#9;&#9;dist = numpy.linalg.norm(dir_vec)<br>
&#9;&#9;p_col = C + dir_vec * (r / dist) if dist &gt; 1e-8 else p_ray<br>
&#9;&#9;return p_col, p_ray, 0.0<br>
&#9;def __init__(self, center: numpy.ndarray, radius: float):<br>
&#9;&#9;self.center = center<br>
&#9;&#9;self.radius = radius<br>
<br>
&#9;def __repr__(self):<br>
&#9;&#9;return f&quot;SphereCollider(center={self.center}, radius={self.radius})&quot;<br>
<br>
&#9;def transform_by(self, transform: 'Pose3'):<br>
&#9;&#9;&quot;&quot;&quot;Return a new SphereCollider transformed by the given Pose3.&quot;&quot;&quot;<br>
&#9;&#9;new_center = transform.transform_point(self.center)<br>
&#9;&#9;return SphereCollider(new_center, self.radius)<br>
<br>
&#9;def closest_to_sphere(self, other: &quot;SphereCollider&quot;):<br>
&#9;&#9;&quot;&quot;&quot;Return the closest points and distance between this sphere and another sphere.&quot;&quot;&quot;<br>
&#9;&#9;center_dist = numpy.linalg.norm(other.center - self.center)<br>
&#9;&#9;dist = center_dist - (self.radius + other.radius)<br>
&#9;&#9;if center_dist &gt; 1e-8:<br>
&#9;&#9;&#9;dir_vec = (other.center - self.center) / center_dist<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;dir_vec = numpy.array([1.0, 0.0, 0.0])  # Arbitrary direction if centers coincide<br>
&#9;&#9;p_near = self.center + dir_vec * self.radius<br>
&#9;&#9;q_near = other.center - dir_vec * other.radius<br>
&#9;&#9;return p_near, q_near, dist<br>
<br>
&#9;def closest_to_capsule(self, other: &quot;CapsuleCollider&quot;):<br>
&#9;&#9;&quot;&quot;&quot;Return the closest points and distance between this sphere and a capsule.&quot;&quot;&quot;<br>
&#9;&#9;p_near, q_near, dist = closest_points_between_capsule_and_sphere(<br>
&#9;&#9;&#9;other.a, other.b, other.radius,<br>
&#9;&#9;&#9;self.center, self.radius)<br>
&#9;&#9;return q_near, p_near, dist<br>
<br>
&#9;def closest_to_union_collider(self, other: &quot;UnionCollider&quot;):<br>
&#9;&#9;&quot;&quot;&quot;Return the closest points and distance between this capsule and a union collider.&quot;&quot;&quot;<br>
&#9;&#9;a,b,c = other.closest_to_collider(self)<br>
&#9;&#9;return b,a,c<br>
&#9;&#9;<br>
&#9;def closest_to_collider(self, other: &quot;Collider&quot;):<br>
&#9;&#9;from .capsule import CapsuleCollider<br>
&#9;&#9;from .union_collider import UnionCollider<br>
<br>
&#9;&#9;&quot;&quot;&quot;Return the closest points and distance between this collider and another collider.&quot;&quot;&quot;<br>
&#9;&#9;if isinstance(other, SphereCollider):<br>
&#9;&#9;&#9;return self.closest_to_sphere(other)<br>
&#9;&#9;elif isinstance(other, CapsuleCollider):<br>
&#9;&#9;&#9;return self.closest_to_capsule(other)<br>
&#9;&#9;elif isinstance(other, UnionCollider):<br>
&#9;&#9;&#9;return self.closest_to_union_collider(other)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;raise NotImplementedError(f&quot;closest_to_collider not implemented for {type(other)}&quot;)<br>
<!-- END SCAT CODE -->
</body>
</html>
