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
    def closest_to_ray(self, ray: &quot;Ray3&quot;):<br>
        &quot;&quot;&quot;<br>
        Ближайшие точки между сегментом капсулы и лучом:<br>
        Реализуем прямой рейкаст в капсулу (цилиндр вдоль [a,b] + две сферы)<br>
        через аналитические уравнения:<br>
            |(w_perp + t * D_perp)|^2 = r^2  — пересечение с цилиндром<br>
            |O + tD - C|^2 = r^2              — пересечение с каждой сферой<br>
        &quot;&quot;&quot;<br>
        from termin.closest import closest_points_between_segments<br>
<br>
        O = ray.origin<br>
        D = ray.direction<br>
        A = self.a<br>
        B = self.b<br>
        r = self.radius<br>
<br>
        axis = B - A<br>
        length = numpy.linalg.norm(axis)<br>
        if length &lt; 1e-8:<br>
            # Вырожденная капсула → сфера.<br>
            return SphereCollider(A, r).closest_to_ray(ray)<br>
<br>
        U = axis / length<br>
<br>
        # Проверяем, стартует ли луч внутри капсулы.<br>
        proj0 = numpy.dot(O - A, U)<br>
        closest_axis_pt = A + numpy.clip(proj0, 0.0, length) * U<br>
        dist_axis0 = numpy.linalg.norm(O - closest_axis_pt)<br>
        if dist_axis0 &lt;= r + 1e-8:<br>
            return O, O, 0.0<br>
<br>
        def sphere_hit(center: numpy.ndarray) -&gt; float | None:<br>
            m = O - center<br>
            b = numpy.dot(m, D)<br>
            c = numpy.dot(m, m) - r * r<br>
            disc = b * b - c<br>
            if disc &lt; 0:<br>
                return None<br>
            sqrt_disc = numpy.sqrt(disc)<br>
            t0 = -b - sqrt_disc<br>
            if t0 &gt;= 0:<br>
                return t0<br>
            t1 = -b + sqrt_disc<br>
            return t1 if t1 &gt;= 0 else None<br>
<br>
        t_candidates = []<br>
<br>
        # Пересечение с цилиндрической частью: |w_perp + t D_perp|^2 = r^2<br>
        w = O - A<br>
        w_par = numpy.dot(w, U)<br>
        w_perp = w - w_par * U<br>
        D_par = numpy.dot(D, U)<br>
        D_perp = D - D_par * U<br>
<br>
        a = numpy.dot(D_perp, D_perp)<br>
        b = 2.0 * numpy.dot(D_perp, w_perp)<br>
        c = numpy.dot(w_perp, w_perp) - r * r<br>
<br>
        if a &gt; 1e-12:<br>
            disc = b * b - 4.0 * a * c<br>
            if disc &gt;= 0.0:<br>
                sqrt_disc = numpy.sqrt(disc)<br>
                t0 = (-b - sqrt_disc) / (2.0 * a)<br>
                t1 = (-b + sqrt_disc) / (2.0 * a)<br>
                for t in (t0, t1):<br>
                    if t &lt; 0:<br>
                        continue<br>
                    s = w_par + t * D_par  # параметр вдоль оси капсулы<br>
                    if 0.0 &lt;= s &lt;= length:<br>
                        t_candidates.append(t)<br>
        else:<br>
            # Луч параллелен оси. Если проекция в пределах радиуса, стукнемся об крышки.<br>
            if c &lt;= 0.0 and (D_par &gt; 0.0 or D_par &lt; 0.0):<br>
                # Попадание в цилиндрическую часть, но точное t определят сферы.<br>
                pass<br>
<br>
        # Пересечения с капами<br>
        t_sphere_a = sphere_hit(A)<br>
        if t_sphere_a is not None:<br>
            t_candidates.append(t_sphere_a)<br>
        t_sphere_b = sphere_hit(B)<br>
        if t_sphere_b is not None:<br>
            t_candidates.append(t_sphere_b)<br>
<br>
        if t_candidates:<br>
            t_hit = min(t_candidates)<br>
            p_hit = ray.point_at(t_hit)<br>
            return p_hit, p_hit, 0.0<br>
<br>
        # Нет пересечения — берем ближайшие точки между лучом (обрезанным) и осью капсулы.<br>
        FAR = 1e6<br>
        p_seg, p_ray, dist_axis = closest_points_between_segments(<br>
            A, B,<br>
            O, O + D * FAR<br>
        )<br>
        dir_vec = p_ray - p_seg<br>
        n = numpy.linalg.norm(dir_vec)<br>
        if n &gt; 1e-8:<br>
            p_col = p_seg + dir_vec * (r / n)<br>
        else:<br>
            # Луч параллелен оси: сдвигаем вдоль любой нормали.<br>
            normal = numpy.cross(U, numpy.array([1.0, 0.0, 0.0]))<br>
            if numpy.linalg.norm(normal) &lt; 1e-8:<br>
                normal = numpy.cross(U, numpy.array([0.0, 1.0, 0.0]))<br>
            normal = normal / numpy.linalg.norm(normal)<br>
            p_col = p_seg + normal * r<br>
        return p_col, p_ray, numpy.linalg.norm(p_col - p_ray)<br>
    <br>
    def __init__(self, a: numpy.ndarray, b: numpy.ndarray, radius: float):<br>
        self.a = a<br>
        self.b = b<br>
        self.radius = radius<br>
<br>
    def transform_by(self, transform: 'Pose3'):<br>
        &quot;&quot;&quot;Return a new CapsuleCollider transformed by the given Pose3.&quot;&quot;&quot;<br>
        new_a = transform.transform_point(self.a)<br>
        new_b = transform.transform_point(self.b)<br>
        return CapsuleCollider(new_a, new_b, self.radius)<br>
    <br>
    def closest_to_capsule(self, other: &quot;CapsuleCollider&quot;):<br>
        &quot;&quot;&quot;Return the closest points and distance between this capsule and another capsule.&quot;&quot;&quot;<br>
        p_near, q_near, dist = closest_points_between_capsules(<br>
            self.a, self.b, self.radius,<br>
            other.a, other.b, other.radius)<br>
        return p_near, q_near, dist<br>
<br>
    def closest_to_sphere(self, other: &quot;SphereCollider&quot;):<br>
        &quot;&quot;&quot;Return the closest points and distance between this capsule and a sphere.&quot;&quot;&quot;<br>
        p_near, q_near, dist = closest_points_between_capsule_and_sphere(<br>
            self.a, self.b, self.radius,<br>
            other.center, other.radius)<br>
        return p_near, q_near, dist<br>
<br>
    def closest_to_union_collider(self, other: &quot;UnionCollider&quot;):<br>
        &quot;&quot;&quot;Return the closest points and distance between this capsule and a union collider.&quot;&quot;&quot;<br>
        a,b,c = other.closest_to_collider(self)<br>
        return b,a,c<br>
<br>
    def closest_to_collider(self, other: &quot;Collider&quot;):<br>
        &quot;&quot;&quot;Return the closest points and distance between this collider and another collider.&quot;&quot;&quot;<br>
<br>
        from .sphere import SphereCollider<br>
        from .union_collider import UnionCollider<br>
<br>
        if isinstance(other, CapsuleCollider):<br>
            return self.closest_to_capsule(other)<br>
        elif isinstance(other, SphereCollider):<br>
            return other.closest_to_sphere(self)<br>
        elif isinstance(other, UnionCollider):<br>
            return self.closest_to_union_collider(other)<br>
        else:<br>
            raise NotImplementedError(f&quot;closest_to_collider not implemented for {type(other)}&quot;)<br>
<br>
    def distance(self, other: &quot;Collider&quot;) -&gt; float:<br>
        &quot;&quot;&quot;Return the distance between this collider and another collider.&quot;&quot;&quot;<br>
        _, _, dist = self.closest_to_collider(other)<br>
        return dist<br>
<!-- END SCAT CODE -->
</body>
</html>
