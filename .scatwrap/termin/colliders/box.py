<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/box.py</title>
</head>
<body>
<!-- BEGIN SCAT CODE -->
from termin.geombase import Pose3, AABB<br>
import numpy<br>
from termin.colliders.collider import Collider<br>
from termin.geomalgo.project import closest_of_aabb_and_capsule, closest_of_aabb_and_sphere<br>
<br>
<br>
<br>
class BoxCollider(Collider):<br>
&#9;def closest_to_ray(self, ray: &quot;Ray3&quot;):<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;Переносим луч в локальное пространство коробки и применяем стандартный<br>
&#9;&#9;алгоритм пересечения луча с AABB.<br>
&#9;&#9;&quot;&quot;&quot;<br>
&#9;&#9;import numpy as np<br>
<br>
&#9;&#9;# Перенос луча в локальные координаты<br>
&#9;&#9;O_local = self.point_in_local_frame(ray.origin)<br>
&#9;&#9;D_local = self.pose.inverse_transform_vector(ray.direction)<br>
<br>
&#9;&#9;# Нормализуем, чтобы корректно считать t<br>
&#9;&#9;n = np.linalg.norm(D_local)<br>
&#9;&#9;if n &lt; 1e-8:<br>
&#9;&#9;&#9;D_local = np.array([0, 0, 1], dtype=np.float32)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;D_local = D_local / n<br>
<br>
&#9;&#9;aabb = self.local_aabb()<br>
<br>
&#9;&#9;tmin = -np.inf<br>
&#9;&#9;tmax =  np.inf<br>
&#9;&#9;hit_possible = True<br>
<br>
&#9;&#9;for i in range(3):<br>
&#9;&#9;&#9;if abs(D_local[i]) &lt; 1e-8:<br>
&#9;&#9;&#9;&#9;# Луч параллелен плоскости AABB, проверяем попадание<br>
&#9;&#9;&#9;&#9;if O_local[i] &lt; aabb.min_point[i] or O_local[i] &gt; aabb.max_point[i]:<br>
&#9;&#9;&#9;&#9;&#9;hit_possible = False<br>
&#9;&#9;&#9;else:<br>
&#9;&#9;&#9;&#9;t1 = (aabb.min_point[i] - O_local[i]) / D_local[i]<br>
&#9;&#9;&#9;&#9;t2 = (aabb.max_point[i] - O_local[i]) / D_local[i]<br>
&#9;&#9;&#9;&#9;t1, t2 = min(t1, t2), max(t1, t2)<br>
&#9;&#9;&#9;&#9;tmin = max(tmin, t1)<br>
&#9;&#9;&#9;&#9;tmax = min(tmax, t2)<br>
<br>
&#9;&#9;# Нет пересечения → ищем ближайшую точку на луче<br>
&#9;&#9;if (not hit_possible) or (tmax &lt; max(tmin, 0)):<br>
&#9;&#9;&#9;candidates = [0.0]<br>
&#9;&#9;&#9;for i in range(3):<br>
&#9;&#9;&#9;&#9;if abs(D_local[i]) &lt; 1e-8:<br>
&#9;&#9;&#9;&#9;&#9;continue<br>
&#9;&#9;&#9;&#9;candidates.append((aabb.min_point[i] - O_local[i]) / D_local[i])<br>
&#9;&#9;&#9;&#9;candidates.append((aabb.max_point[i] - O_local[i]) / D_local[i])<br>
<br>
&#9;&#9;&#9;best_t = 0.0<br>
&#9;&#9;&#9;best_dist = float(&quot;inf&quot;)<br>
&#9;&#9;&#9;for t in candidates:<br>
&#9;&#9;&#9;&#9;if t &lt; 0:<br>
&#9;&#9;&#9;&#9;&#9;continue<br>
&#9;&#9;&#9;&#9;p_ray_local = O_local + D_local * t<br>
&#9;&#9;&#9;&#9;p_box_local = np.minimum(np.maximum(p_ray_local, aabb.min_point), aabb.max_point)<br>
&#9;&#9;&#9;&#9;dist = np.linalg.norm(p_box_local - p_ray_local)<br>
&#9;&#9;&#9;&#9;if dist &lt; best_dist:<br>
&#9;&#9;&#9;&#9;&#9;best_dist = dist<br>
&#9;&#9;&#9;&#9;&#9;best_t = t<br>
<br>
&#9;&#9;&#9;p_ray = ray.point_at(best_t)<br>
&#9;&#9;&#9;p_box_local = O_local + D_local * best_t<br>
&#9;&#9;&#9;p_box_local = np.minimum(np.maximum(p_box_local, aabb.min_point), aabb.max_point)<br>
&#9;&#9;&#9;p_col = self.pose.transform_point(p_box_local)<br>
&#9;&#9;&#9;return p_col, p_ray, best_dist<br>
<br>
&#9;&#9;# Есть пересечение, используем t_hit ≥ 0<br>
&#9;&#9;t_hit = tmin if tmin &gt;= 0 else tmax<br>
&#9;&#9;if t_hit &lt; 0:<br>
&#9;&#9;&#9;t_hit = tmax<br>
<br>
&#9;&#9;p_ray_local = O_local + D_local * t_hit<br>
&#9;&#9;p_ray = ray.point_at(t_hit)<br>
&#9;&#9;# точка попадания лежит в AABB, трансформируем в мир<br>
&#9;&#9;p_col = p_ray<br>
&#9;&#9;return p_col, p_ray, 0.0<br>
&#9;<br>
&#9;def __init__(self, center : numpy.ndarray = None, size: numpy.ndarray = None, pose: Pose3 = Pose3.identity()):<br>
&#9;&#9;self.center = center<br>
&#9;&#9;self.size = size<br>
&#9;&#9;self.pose = pose<br>
<br>
&#9;&#9;if self.center is None:<br>
&#9;&#9;&#9;self.center = numpy.array([0.0, 0.0, 0.0], dtype=numpy.float32)<br>
&#9;&#9;if self.size is None:<br>
&#9;&#9;&#9;self.size = numpy.array([1.0, 1.0, 1.0], dtype=numpy.float32)<br>
<br>
&#9;def local_aabb(self) -&gt; AABB:<br>
&#9;&#9;half_size = self.size / 2.0<br>
&#9;&#9;min_point = self.center - half_size<br>
&#9;&#9;max_point = self.center + half_size<br>
&#9;&#9;return AABB(min_point, max_point)<br>
<br>
&#9;def __repr__(self):<br>
&#9;&#9;return f&quot;BoxCollider(center={self.center}, size={self.size}, pose={self.pose})&quot;<br>
<br>
&#9;def transform_by(self, tpose: 'Pose3'):<br>
&#9;&#9;new_pose = tpose.compose(self.pose)<br>
&#9;&#9;return BoxCollider(self.center, self.size, new_pose)<br>
<br>
&#9;def point_in_local_frame(self, point: numpy.ndarray) -&gt; numpy.ndarray:<br>
&#9;&#9;&quot;&quot;&quot;Transform point to local frame&quot;&quot;&quot;<br>
&#9;&#9;return self.pose.inverse_transform_point(point)<br>
<br>
&#9;def segment_in_local_frame(self, seg_start: numpy.ndarray, seg_end: numpy.ndarray):<br>
&#9;&#9;&quot;&quot;&quot;Transform segment to local frame&quot;&quot;&quot;<br>
&#9;&#9;local_start = self.point_in_local_frame(seg_start)<br>
&#9;&#9;local_end = self.point_in_local_frame(seg_end)<br>
&#9;&#9;return local_start, local_end<br>
&#9;<br>
&#9;def closest_point_to_capsule(self, capsule : &quot;CapsuleCollider&quot;):<br>
&#9;&#9;a_local = self.point_in_local_frame(capsule.a)<br>
&#9;&#9;b_local = self.point_in_local_frame(capsule.b)<br>
&#9;&#9;aabb = self.local_aabb()<br>
&#9;&#9;closest_aabb_point, closest_capsule_point, distance = closest_of_aabb_and_capsule(<br>
&#9;&#9;&#9;aabb.min_point, aabb.max_point,<br>
&#9;&#9;&#9;a_local, b_local, capsule.radius<br>
&#9;&#9;)<br>
<br>
&#9;&#9;# Transform closest points back to world frame<br>
&#9;&#9;closest_aabb_point_world = self.pose.transform_point(closest_aabb_point)<br>
&#9;&#9;closest_capsule_point_world = self.pose.transform_point(closest_capsule_point)<br>
&#9;&#9;return closest_aabb_point_world, closest_capsule_point_world, distance<br>
&#9;<br>
&#9;def closest_to_sphere(self, sphere : &quot;SphereCollider&quot;):<br>
&#9;&#9;c_local = self.point_in_local_frame(sphere.center)<br>
&#9;&#9;aabb = self.local_aabb()<br>
&#9;&#9;closest_aabb_point, closest_sphere_point, distance = closest_of_aabb_and_sphere(<br>
&#9;&#9;&#9;aabb.min_point, aabb.max_point,<br>
&#9;&#9;&#9;c_local, sphere.radius<br>
&#9;&#9;)<br>
<br>
&#9;&#9;# Transform closest points back to world frame<br>
&#9;&#9;closest_aabb_point_world = self.pose.transform_point(closest_aabb_point)<br>
&#9;&#9;closest_sphere_point_world = self.pose.transform_point(closest_sphere_point)<br>
&#9;&#9;return closest_aabb_point_world, closest_sphere_point_world, distance<br>
<br>
&#9;def closest_to_collider(self, other: &quot;Collider&quot;):<br>
&#9;&#9;from .capsule import CapsuleCollider<br>
&#9;&#9;from .sphere import SphereCollider<br>
&#9;&#9;if isinstance(other, CapsuleCollider):<br>
&#9;&#9;&#9;return self.closest_point_to_capsule(other)<br>
&#9;&#9;elif isinstance(other, SphereCollider):<br>
&#9;&#9;&#9;return self.closest_to_sphere(other)<br>
&#9;&#9;else:<br>
&#9;&#9;&#9;raise NotImplementedError(f&quot;closest_to_collider not implemented for {type(other)}&quot;)<br>
<!-- END SCAT CODE -->
</body>
</html>
