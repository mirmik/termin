<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/box.py</title>
</head>
<body>
<pre><code>
from termin.geombase import Pose3, AABB
import numpy
from termin.colliders.collider import Collider
from termin.geomalgo.project import closest_of_aabb_and_capsule, closest_of_aabb_and_sphere



class BoxCollider(Collider):
    def closest_to_ray(self, ray: &quot;Ray3&quot;):
        &quot;&quot;&quot;
        Переносим луч в локальное пространство коробки и применяем стандартный
        алгоритм пересечения луча с AABB.
        &quot;&quot;&quot;
        import numpy as np

        # Перенос луча в локальные координаты
        O_local = self.point_in_local_frame(ray.origin)
        D_local = self.pose.inverse_transform_vector(ray.direction)

        # Нормализуем, чтобы корректно считать t
        n = np.linalg.norm(D_local)
        if n &lt; 1e-8:
            D_local = np.array([0, 0, 1], dtype=np.float32)
        else:
            D_local = D_local / n

        aabb = self.local_aabb()

        tmin = -np.inf
        tmax =  np.inf
        hit_possible = True

        for i in range(3):
            if abs(D_local[i]) &lt; 1e-8:
                # Луч параллелен плоскости AABB, проверяем попадание
                if O_local[i] &lt; aabb.min_point[i] or O_local[i] &gt; aabb.max_point[i]:
                    hit_possible = False
            else:
                t1 = (aabb.min_point[i] - O_local[i]) / D_local[i]
                t2 = (aabb.max_point[i] - O_local[i]) / D_local[i]
                t1, t2 = min(t1, t2), max(t1, t2)
                tmin = max(tmin, t1)
                tmax = min(tmax, t2)

        # Нет пересечения → ищем ближайшую точку на луче
        if (not hit_possible) or (tmax &lt; max(tmin, 0)):
            candidates = [0.0]
            for i in range(3):
                if abs(D_local[i]) &lt; 1e-8:
                    continue
                candidates.append((aabb.min_point[i] - O_local[i]) / D_local[i])
                candidates.append((aabb.max_point[i] - O_local[i]) / D_local[i])

            best_t = 0.0
            best_dist = float(&quot;inf&quot;)
            for t in candidates:
                if t &lt; 0:
                    continue
                p_ray_local = O_local + D_local * t
                p_box_local = np.minimum(np.maximum(p_ray_local, aabb.min_point), aabb.max_point)
                dist = np.linalg.norm(p_box_local - p_ray_local)
                if dist &lt; best_dist:
                    best_dist = dist
                    best_t = t

            p_ray = ray.point_at(best_t)
            p_box_local = O_local + D_local * best_t
            p_box_local = np.minimum(np.maximum(p_box_local, aabb.min_point), aabb.max_point)
            p_col = self.pose.transform_point(p_box_local)
            return p_col, p_ray, best_dist

        # Есть пересечение, используем t_hit ≥ 0
        t_hit = tmin if tmin &gt;= 0 else tmax
        if t_hit &lt; 0:
            t_hit = tmax

        p_ray_local = O_local + D_local * t_hit
        p_ray = ray.point_at(t_hit)
        # точка попадания лежит в AABB, трансформируем в мир
        p_col = p_ray
        return p_col, p_ray, 0.0
    
    def __init__(self, center : numpy.ndarray = None, size: numpy.ndarray = None, pose: Pose3 = Pose3.identity()):
        self.center = center
        self.size = size
        self.pose = pose

        if self.center is None:
            self.center = numpy.array([0.0, 0.0, 0.0], dtype=numpy.float32)
        if self.size is None:
            self.size = numpy.array([1.0, 1.0, 1.0], dtype=numpy.float32)

    def local_aabb(self) -&gt; AABB:
        half_size = self.size / 2.0
        min_point = self.center - half_size
        max_point = self.center + half_size
        return AABB(min_point, max_point)

    def __repr__(self):
        return f&quot;BoxCollider(center={self.center}, size={self.size}, pose={self.pose})&quot;

    def transform_by(self, tpose: 'Pose3'):
        new_pose = tpose.compose(self.pose)
        return BoxCollider(self.center, self.size, new_pose)

    def point_in_local_frame(self, point: numpy.ndarray) -&gt; numpy.ndarray:
        &quot;&quot;&quot;Transform point to local frame&quot;&quot;&quot;
        return self.pose.inverse_transform_point(point)

    def segment_in_local_frame(self, seg_start: numpy.ndarray, seg_end: numpy.ndarray):
        &quot;&quot;&quot;Transform segment to local frame&quot;&quot;&quot;
        local_start = self.point_in_local_frame(seg_start)
        local_end = self.point_in_local_frame(seg_end)
        return local_start, local_end
    
    def closest_point_to_capsule(self, capsule : &quot;CapsuleCollider&quot;):
        a_local = self.point_in_local_frame(capsule.a)
        b_local = self.point_in_local_frame(capsule.b)
        aabb = self.local_aabb()
        closest_aabb_point, closest_capsule_point, distance = closest_of_aabb_and_capsule(
            aabb.min_point, aabb.max_point,
            a_local, b_local, capsule.radius
        )

        # Transform closest points back to world frame
        closest_aabb_point_world = self.pose.transform_point(closest_aabb_point)
        closest_capsule_point_world = self.pose.transform_point(closest_capsule_point)
        return closest_aabb_point_world, closest_capsule_point_world, distance
    
    def closest_to_sphere(self, sphere : &quot;SphereCollider&quot;):
        c_local = self.point_in_local_frame(sphere.center)
        aabb = self.local_aabb()
        closest_aabb_point, closest_sphere_point, distance = closest_of_aabb_and_sphere(
            aabb.min_point, aabb.max_point,
            c_local, sphere.radius
        )

        # Transform closest points back to world frame
        closest_aabb_point_world = self.pose.transform_point(closest_aabb_point)
        closest_sphere_point_world = self.pose.transform_point(closest_sphere_point)
        return closest_aabb_point_world, closest_sphere_point_world, distance

    def closest_to_collider(self, other: &quot;Collider&quot;):
        from .capsule import CapsuleCollider
        from .sphere import SphereCollider
        if isinstance(other, CapsuleCollider):
            return self.closest_point_to_capsule(other)
        elif isinstance(other, SphereCollider):
            return self.closest_to_sphere(other)
        else:
            raise NotImplementedError(f&quot;closest_to_collider not implemented for {type(other)}&quot;)

</code></pre>
</body>
</html>
