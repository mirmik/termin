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
    def closest_to_ray(self, ray: &quot;Ray3&quot;):<br>
        &quot;&quot;&quot;<br>
        Аналитическое пересечение луча со сферой.<br>
        Луч: O + D * t<br>
        Центр: C<br>
        Радиус: r<br>
        &quot;&quot;&quot;<br>
        O = ray.origin<br>
        D = ray.direction<br>
        C = self.center<br>
        r = self.radius<br>
<br>
        OC = O - C<br>
        b = 2 * numpy.dot(D, OC)<br>
        c = numpy.dot(OC, OC) - r * r<br>
        disc = b * b - 4 * c<br>
<br>
        # Нет пересечения — вернуть ближайшие точки<br>
        if disc &lt; 0:<br>
            # t = -dot(OC, D)<br>
            #t = -numpy.dot(OC, D)<br>
            t = numpy.dot((C - O), D)<br>
            if t &lt; 0:<br>
                t = 0<br>
            p_ray = ray.point_at(t)<br>
<br>
            dir_vec = p_ray - C<br>
            dist = numpy.linalg.norm(dir_vec)<br>
            if dist &gt; 1e-8:<br>
                p_col = C + dir_vec * (r / dist)<br>
            else:<br>
                p_col = C + numpy.array([r, 0, 0], dtype=numpy.float32)  # произвольное направление<br>
<br>
            return p_col, p_ray, numpy.linalg.norm(p_col - p_ray)<br>
<br>
        # Есть пересечения: берем ближайшее t &gt;= 0<br>
        sqrt_disc = numpy.sqrt(disc)<br>
        t1 = (-b - sqrt_disc) * 0.5<br>
        t2 = (-b + sqrt_disc) * 0.5<br>
<br>
        t_hit = None<br>
        if t1 &gt;= 0:<br>
            t_hit = t1<br>
        elif t2 &gt;= 0:<br>
            t_hit = t2<br>
<br>
        # Пересечение позади луча — перейти к ближайшей точке<br>
        if t_hit is None:<br>
            t = -numpy.dot(OC, D)<br>
            if t &lt; 0:<br>
                t = 0<br>
            p_ray = ray.point_at(t)<br>
            dir_vec = p_ray - C<br>
            dist = numpy.linalg.norm(dir_vec)<br>
            p_col = C + dir_vec * (r / dist)<br>
            return p_col, p_ray, numpy.linalg.norm(p_col - p_ray)<br>
<br>
        # Корректное пересечение<br>
        p_ray = ray.point_at(t_hit)<br>
        dir_vec = p_ray - C<br>
        dist = numpy.linalg.norm(dir_vec)<br>
        p_col = C + dir_vec * (r / dist) if dist &gt; 1e-8 else p_ray<br>
        return p_col, p_ray, 0.0<br>
    def __init__(self, center: numpy.ndarray, radius: float):<br>
        self.center = center<br>
        self.radius = radius<br>
<br>
    def __repr__(self):<br>
        return f&quot;SphereCollider(center={self.center}, radius={self.radius})&quot;<br>
<br>
    def transform_by(self, transform: 'Pose3'):<br>
        &quot;&quot;&quot;Return a new SphereCollider transformed by the given Pose3.&quot;&quot;&quot;<br>
        new_center = transform.transform_point(self.center)<br>
        return SphereCollider(new_center, self.radius)<br>
<br>
    def closest_to_sphere(self, other: &quot;SphereCollider&quot;):<br>
        &quot;&quot;&quot;Return the closest points and distance between this sphere and another sphere.&quot;&quot;&quot;<br>
        center_dist = numpy.linalg.norm(other.center - self.center)<br>
        dist = center_dist - (self.radius + other.radius)<br>
        if center_dist &gt; 1e-8:<br>
            dir_vec = (other.center - self.center) / center_dist<br>
        else:<br>
            dir_vec = numpy.array([1.0, 0.0, 0.0])  # Arbitrary direction if centers coincide<br>
        p_near = self.center + dir_vec * self.radius<br>
        q_near = other.center - dir_vec * other.radius<br>
        return p_near, q_near, dist<br>
<br>
    def closest_to_capsule(self, other: &quot;CapsuleCollider&quot;):<br>
        &quot;&quot;&quot;Return the closest points and distance between this sphere and a capsule.&quot;&quot;&quot;<br>
        p_near, q_near, dist = closest_points_between_capsule_and_sphere(<br>
            other.a, other.b, other.radius,<br>
            self.center, self.radius)<br>
        return q_near, p_near, dist<br>
<br>
    def closest_to_union_collider(self, other: &quot;UnionCollider&quot;):<br>
        &quot;&quot;&quot;Return the closest points and distance between this capsule and a union collider.&quot;&quot;&quot;<br>
        a,b,c = other.closest_to_collider(self)<br>
        return b,a,c<br>
        <br>
    def closest_to_collider(self, other: &quot;Collider&quot;):<br>
        from .capsule import CapsuleCollider<br>
        from .union_collider import UnionCollider<br>
<br>
        &quot;&quot;&quot;Return the closest points and distance between this collider and another collider.&quot;&quot;&quot;<br>
        if isinstance(other, SphereCollider):<br>
            return self.closest_to_sphere(other)<br>
        elif isinstance(other, CapsuleCollider):<br>
            return self.closest_to_capsule(other)<br>
        elif isinstance(other, UnionCollider):<br>
            return self.closest_to_union_collider(other)<br>
        else:<br>
            raise NotImplementedError(f&quot;closest_to_collider not implemented for {type(other)}&quot;)<br>
<!-- END SCAT CODE -->
</body>
</html>
