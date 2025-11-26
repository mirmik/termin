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
    def closest_to_ray(self, ray: &quot;Ray3&quot;):<br>
        &quot;&quot;&quot;<br>
        Переносим луч в локальное пространство коробки и применяем стандартный<br>
        алгоритм пересечения луча с AABB.<br>
        &quot;&quot;&quot;<br>
        import numpy as np<br>
<br>
        # Перенос луча в локальные координаты<br>
        O_local = self.point_in_local_frame(ray.origin)<br>
        D_local = self.pose.inverse_transform_vector(ray.direction)<br>
<br>
        # Нормализуем, чтобы корректно считать t<br>
        n = np.linalg.norm(D_local)<br>
        if n &lt; 1e-8:<br>
            D_local = np.array([0, 0, 1], dtype=np.float32)<br>
        else:<br>
            D_local = D_local / n<br>
<br>
        aabb = self.local_aabb()<br>
<br>
        tmin = -np.inf<br>
        tmax =  np.inf<br>
        hit_possible = True<br>
<br>
        for i in range(3):<br>
            if abs(D_local[i]) &lt; 1e-8:<br>
                # Луч параллелен плоскости AABB, проверяем попадание<br>
                if O_local[i] &lt; aabb.min_point[i] or O_local[i] &gt; aabb.max_point[i]:<br>
                    hit_possible = False<br>
            else:<br>
                t1 = (aabb.min_point[i] - O_local[i]) / D_local[i]<br>
                t2 = (aabb.max_point[i] - O_local[i]) / D_local[i]<br>
                t1, t2 = min(t1, t2), max(t1, t2)<br>
                tmin = max(tmin, t1)<br>
                tmax = min(tmax, t2)<br>
<br>
        # Нет пересечения → ищем ближайшую точку на луче<br>
        if (not hit_possible) or (tmax &lt; max(tmin, 0)):<br>
            candidates = [0.0]<br>
            for i in range(3):<br>
                if abs(D_local[i]) &lt; 1e-8:<br>
                    continue<br>
                candidates.append((aabb.min_point[i] - O_local[i]) / D_local[i])<br>
                candidates.append((aabb.max_point[i] - O_local[i]) / D_local[i])<br>
<br>
            best_t = 0.0<br>
            best_dist = float(&quot;inf&quot;)<br>
            for t in candidates:<br>
                if t &lt; 0:<br>
                    continue<br>
                p_ray_local = O_local + D_local * t<br>
                p_box_local = np.minimum(np.maximum(p_ray_local, aabb.min_point), aabb.max_point)<br>
                dist = np.linalg.norm(p_box_local - p_ray_local)<br>
                if dist &lt; best_dist:<br>
                    best_dist = dist<br>
                    best_t = t<br>
<br>
            p_ray = ray.point_at(best_t)<br>
            p_box_local = O_local + D_local * best_t<br>
            p_box_local = np.minimum(np.maximum(p_box_local, aabb.min_point), aabb.max_point)<br>
            p_col = self.pose.transform_point(p_box_local)<br>
            return p_col, p_ray, best_dist<br>
<br>
        # Есть пересечение, используем t_hit ≥ 0<br>
        t_hit = tmin if tmin &gt;= 0 else tmax<br>
        if t_hit &lt; 0:<br>
            t_hit = tmax<br>
<br>
        p_ray_local = O_local + D_local * t_hit<br>
        p_ray = ray.point_at(t_hit)<br>
        # точка попадания лежит в AABB, трансформируем в мир<br>
        p_col = p_ray<br>
        return p_col, p_ray, 0.0<br>
    <br>
    def __init__(self, center : numpy.ndarray = None, size: numpy.ndarray = None, pose: Pose3 = Pose3.identity()):<br>
        self.center = center<br>
        self.size = size<br>
        self.pose = pose<br>
<br>
        if self.center is None:<br>
            self.center = numpy.array([0.0, 0.0, 0.0], dtype=numpy.float32)<br>
        if self.size is None:<br>
            self.size = numpy.array([1.0, 1.0, 1.0], dtype=numpy.float32)<br>
<br>
    def local_aabb(self) -&gt; AABB:<br>
        half_size = self.size / 2.0<br>
        min_point = self.center - half_size<br>
        max_point = self.center + half_size<br>
        return AABB(min_point, max_point)<br>
<br>
    def __repr__(self):<br>
        return f&quot;BoxCollider(center={self.center}, size={self.size}, pose={self.pose})&quot;<br>
<br>
    def transform_by(self, tpose: 'Pose3'):<br>
        new_pose = tpose.compose(self.pose)<br>
        return BoxCollider(self.center, self.size, new_pose)<br>
<br>
    def point_in_local_frame(self, point: numpy.ndarray) -&gt; numpy.ndarray:<br>
        &quot;&quot;&quot;Transform point to local frame&quot;&quot;&quot;<br>
        return self.pose.inverse_transform_point(point)<br>
<br>
    def segment_in_local_frame(self, seg_start: numpy.ndarray, seg_end: numpy.ndarray):<br>
        &quot;&quot;&quot;Transform segment to local frame&quot;&quot;&quot;<br>
        local_start = self.point_in_local_frame(seg_start)<br>
        local_end = self.point_in_local_frame(seg_end)<br>
        return local_start, local_end<br>
    <br>
    def closest_point_to_capsule(self, capsule : &quot;CapsuleCollider&quot;):<br>
        a_local = self.point_in_local_frame(capsule.a)<br>
        b_local = self.point_in_local_frame(capsule.b)<br>
        aabb = self.local_aabb()<br>
        closest_aabb_point, closest_capsule_point, distance = closest_of_aabb_and_capsule(<br>
            aabb.min_point, aabb.max_point,<br>
            a_local, b_local, capsule.radius<br>
        )<br>
<br>
        # Transform closest points back to world frame<br>
        closest_aabb_point_world = self.pose.transform_point(closest_aabb_point)<br>
        closest_capsule_point_world = self.pose.transform_point(closest_capsule_point)<br>
        return closest_aabb_point_world, closest_capsule_point_world, distance<br>
    <br>
    def closest_to_sphere(self, sphere : &quot;SphereCollider&quot;):<br>
        c_local = self.point_in_local_frame(sphere.center)<br>
        aabb = self.local_aabb()<br>
        closest_aabb_point, closest_sphere_point, distance = closest_of_aabb_and_sphere(<br>
            aabb.min_point, aabb.max_point,<br>
            c_local, sphere.radius<br>
        )<br>
<br>
        # Transform closest points back to world frame<br>
        closest_aabb_point_world = self.pose.transform_point(closest_aabb_point)<br>
        closest_sphere_point_world = self.pose.transform_point(closest_sphere_point)<br>
        return closest_aabb_point_world, closest_sphere_point_world, distance<br>
<br>
    def closest_to_collider(self, other: &quot;Collider&quot;):<br>
        from .capsule import CapsuleCollider<br>
        from .sphere import SphereCollider<br>
        if isinstance(other, CapsuleCollider):<br>
            return self.closest_point_to_capsule(other)<br>
        elif isinstance(other, SphereCollider):<br>
            return self.closest_to_sphere(other)<br>
        else:<br>
            raise NotImplementedError(f&quot;closest_to_collider not implemented for {type(other)}&quot;)<br>
<!-- END SCAT CODE -->
</body>
</html>
