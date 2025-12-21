from termin.geombase import Pose3, AABB
import numpy
from termin.colliders.collider import Collider
from termin.geomalgo.project import closest_of_aabb_and_capsule, closest_of_aabb_and_sphere



class BoxCollider(Collider):
    def closest_to_ray(self, ray: "Ray3"):
        """
        Переносим луч в локальное пространство коробки и применяем стандартный
        алгоритм пересечения луча с AABB.
        """
        import numpy as np

        # Перенос луча в локальные координаты
        O_local = self.point_in_local_frame(ray.origin)
        D_local = self.pose.inverse_transform_vector(ray.direction)

        # Нормализуем, чтобы корректно считать t
        n = np.linalg.norm(D_local)
        if n < 1e-8:
            D_local = np.array([0, 0, 1], dtype=np.float32)
        else:
            D_local = D_local / n

        aabb = self.local_aabb()

        tmin = -np.inf
        tmax =  np.inf
        hit_possible = True

        for i in range(3):
            if abs(D_local[i]) < 1e-8:
                # Луч параллелен плоскости AABB, проверяем попадание
                if O_local[i] < aabb.min_point[i] or O_local[i] > aabb.max_point[i]:
                    hit_possible = False
            else:
                t1 = (aabb.min_point[i] - O_local[i]) / D_local[i]
                t2 = (aabb.max_point[i] - O_local[i]) / D_local[i]
                t1, t2 = min(t1, t2), max(t1, t2)
                tmin = max(tmin, t1)
                tmax = min(tmax, t2)

        # Нет пересечения → ищем ближайшую точку на луче
        if (not hit_possible) or (tmax < max(tmin, 0)):
            candidates = [0.0]
            for i in range(3):
                if abs(D_local[i]) < 1e-8:
                    continue
                candidates.append((aabb.min_point[i] - O_local[i]) / D_local[i])
                candidates.append((aabb.max_point[i] - O_local[i]) / D_local[i])

            best_t = 0.0
            best_dist = float("inf")
            for t in candidates:
                if t < 0:
                    continue
                p_ray_local = O_local + D_local * t
                p_box_local = np.minimum(np.maximum(p_ray_local, aabb.min_point), aabb.max_point)
                dist = np.linalg.norm(p_box_local - p_ray_local)
                if dist < best_dist:
                    best_dist = dist
                    best_t = t

            p_ray = ray.point_at(best_t)
            p_box_local = O_local + D_local * best_t
            p_box_local = np.minimum(np.maximum(p_box_local, aabb.min_point), aabb.max_point)
            p_col = self.pose.transform_point(p_box_local)
            return p_col, p_ray, best_dist

        # Есть пересечение, используем t_hit ≥ 0
        t_hit = tmin if tmin >= 0 else tmax
        if t_hit < 0:
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

    def local_aabb(self) -> AABB:
        half_size = self.size / 2.0
        min_point = self.center - half_size
        max_point = self.center + half_size
        return AABB(min_point, max_point)

    def __repr__(self):
        return f"BoxCollider(center={self.center}, size={self.size}, pose={self.pose})"

    def transform_by(self, tpose: 'Pose3'):
        new_pose = tpose * self.pose
        return BoxCollider(self.center, self.size, new_pose)

    def scale_by(self, scale: numpy.ndarray):
        """Return a new BoxCollider with scaled size."""
        new_size = self.size * scale
        new_center = self.center * scale
        return BoxCollider(new_center, new_size, self.pose)

    def point_in_local_frame(self, point: numpy.ndarray) -> numpy.ndarray:
        """Transform point to local frame"""
        return self.pose.inverse_transform_point(point)

    def segment_in_local_frame(self, seg_start: numpy.ndarray, seg_end: numpy.ndarray):
        """Transform segment to local frame"""
        local_start = self.point_in_local_frame(seg_start)
        local_end = self.point_in_local_frame(seg_end)
        return local_start, local_end
    
    def closest_point_to_capsule(self, capsule : "CapsuleCollider"):
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
    
    def closest_to_sphere(self, sphere : "SphereCollider"):
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

    def closest_to_box(self, other: "BoxCollider"):
        """
        Box-Box collision using SAT (Separating Axis Theorem).
        Returns (point_on_self, point_on_other, distance).
        Distance is negative if penetrating.

        For penetrating boxes, point_on_self contains the contact normal
        (hack to pass extra info without changing API).
        """
        import numpy as np

        # Get world-space centers and rotation matrices
        center_a = self.pose.transform_point(self.center)
        center_b = other.pose.transform_point(other.center)

        R_a = self.pose.rotation_matrix()
        R_b = other.pose.rotation_matrix()

        half_a = self.size / 2.0
        half_b = other.size / 2.0

        # Axes of box A (columns of rotation matrix)
        axes_a = [R_a[:, i] for i in range(3)]
        # Axes of box B
        axes_b = [R_b[:, i] for i in range(3)]

        # Vector from center A to center B
        d = center_b - center_a

        # SAT: test 15 axes
        min_overlap = float('inf')
        best_axis = None

        def project_box(center, axes, half_extents, axis):
            """Project box onto axis, return (min, max)."""
            c_proj = np.dot(center, axis)
            r = sum(abs(np.dot(axes[i], axis)) * half_extents[i] for i in range(3))
            return c_proj - r, c_proj + r

        def test_axis(axis):
            nonlocal min_overlap, best_axis

            length = np.linalg.norm(axis)
            if length < 1e-8:
                return True  # Degenerate axis, skip

            axis = axis / length

            min_a, max_a = project_box(center_a, axes_a, half_a, axis)
            min_b, max_b = project_box(center_b, axes_b, half_b, axis)

            # Check overlap
            if max_a < min_b or max_b < min_a:
                return False  # Separating axis found

            # Calculate overlap
            overlap = min(max_a, max_b) - max(min_a, min_b)
            if overlap < min_overlap:
                min_overlap = overlap
                # Make axis point from A to B
                if np.dot(d, axis) < 0:
                    axis = -axis
                best_axis = axis.copy()

            return True

        # Test face normals of A
        for i in range(3):
            if not test_axis(axes_a[i]):
                # Separating axis found - boxes don't collide
                # Find closest points (approximate)
                p_a = center_a + np.clip(d, -half_a, half_a)
                p_b = center_b + np.clip(-d, -half_b, half_b)
                return p_a, p_b, np.linalg.norm(p_b - p_a)

        # Test face normals of B
        for i in range(3):
            if not test_axis(axes_b[i]):
                p_a = center_a + np.clip(d, -half_a, half_a)
                p_b = center_b + np.clip(-d, -half_b, half_b)
                return p_a, p_b, np.linalg.norm(p_b - p_a)

        # Test edge-edge cross products
        for i in range(3):
            for j in range(3):
                axis = np.cross(axes_a[i], axes_b[j])
                if not test_axis(axis):
                    p_a = center_a + np.clip(d, -half_a, half_a)
                    p_b = center_b + np.clip(-d, -half_b, half_b)
                    return p_a, p_b, np.linalg.norm(p_b - p_a)

        # Boxes are colliding - find contact point
        # Use the axis with minimum penetration
        if best_axis is None:
            best_axis = np.array([0, 0, 1], dtype=np.float64)

        penetration = min_overlap
        contact_point = (center_a + center_b) / 2.0

        # Return: (contact_normal, contact_point, -penetration)
        # Using p_a slot for normal since we're penetrating
        return best_axis, contact_point, -penetration

    def closest_to_collider(self, other: "Collider"):
        from .capsule import CapsuleCollider
        from .sphere import SphereCollider
        if isinstance(other, CapsuleCollider):
            return self.closest_point_to_capsule(other)
        elif isinstance(other, SphereCollider):
            return self.closest_to_sphere(other)
        elif isinstance(other, BoxCollider):
            return self.closest_to_box(other)
        else:
            raise NotImplementedError(f"closest_to_collider not implemented for {type(other)}")
