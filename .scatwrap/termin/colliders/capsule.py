<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>termin/colliders/capsule.py</title>
</head>
<body>
<pre><code>

from termin.closest import closest_points_between_segments, closest_points_between_capsules, closest_points_between_capsule_and_sphere
import numpy
from termin.colliders.collider import Collider
from termin.colliders.sphere import SphereCollider

class CapsuleCollider(Collider):
    def closest_to_ray(self, ray: &quot;Ray3&quot;):
        &quot;&quot;&quot;
        Ближайшие точки между сегментом капсулы и лучом:
        Реализуем прямой рейкаст в капсулу (цилиндр вдоль [a,b] + две сферы)
        через аналитические уравнения:
            |(w_perp + t * D_perp)|^2 = r^2  — пересечение с цилиндром
            |O + tD - C|^2 = r^2              — пересечение с каждой сферой
        &quot;&quot;&quot;
        from termin.closest import closest_points_between_segments

        O = ray.origin
        D = ray.direction
        A = self.a
        B = self.b
        r = self.radius

        axis = B - A
        length = numpy.linalg.norm(axis)
        if length &lt; 1e-8:
            # Вырожденная капсула → сфера.
            return SphereCollider(A, r).closest_to_ray(ray)

        U = axis / length

        # Проверяем, стартует ли луч внутри капсулы.
        proj0 = numpy.dot(O - A, U)
        closest_axis_pt = A + numpy.clip(proj0, 0.0, length) * U
        dist_axis0 = numpy.linalg.norm(O - closest_axis_pt)
        if dist_axis0 &lt;= r + 1e-8:
            return O, O, 0.0

        def sphere_hit(center: numpy.ndarray) -&gt; float | None:
            m = O - center
            b = numpy.dot(m, D)
            c = numpy.dot(m, m) - r * r
            disc = b * b - c
            if disc &lt; 0:
                return None
            sqrt_disc = numpy.sqrt(disc)
            t0 = -b - sqrt_disc
            if t0 &gt;= 0:
                return t0
            t1 = -b + sqrt_disc
            return t1 if t1 &gt;= 0 else None

        t_candidates = []

        # Пересечение с цилиндрической частью: |w_perp + t D_perp|^2 = r^2
        w = O - A
        w_par = numpy.dot(w, U)
        w_perp = w - w_par * U
        D_par = numpy.dot(D, U)
        D_perp = D - D_par * U

        a = numpy.dot(D_perp, D_perp)
        b = 2.0 * numpy.dot(D_perp, w_perp)
        c = numpy.dot(w_perp, w_perp) - r * r

        if a &gt; 1e-12:
            disc = b * b - 4.0 * a * c
            if disc &gt;= 0.0:
                sqrt_disc = numpy.sqrt(disc)
                t0 = (-b - sqrt_disc) / (2.0 * a)
                t1 = (-b + sqrt_disc) / (2.0 * a)
                for t in (t0, t1):
                    if t &lt; 0:
                        continue
                    s = w_par + t * D_par  # параметр вдоль оси капсулы
                    if 0.0 &lt;= s &lt;= length:
                        t_candidates.append(t)
        else:
            # Луч параллелен оси. Если проекция в пределах радиуса, стукнемся об крышки.
            if c &lt;= 0.0 and (D_par &gt; 0.0 or D_par &lt; 0.0):
                # Попадание в цилиндрическую часть, но точное t определят сферы.
                pass

        # Пересечения с капами
        t_sphere_a = sphere_hit(A)
        if t_sphere_a is not None:
            t_candidates.append(t_sphere_a)
        t_sphere_b = sphere_hit(B)
        if t_sphere_b is not None:
            t_candidates.append(t_sphere_b)

        if t_candidates:
            t_hit = min(t_candidates)
            p_hit = ray.point_at(t_hit)
            return p_hit, p_hit, 0.0

        # Нет пересечения — берем ближайшие точки между лучом (обрезанным) и осью капсулы.
        FAR = 1e6
        p_seg, p_ray, dist_axis = closest_points_between_segments(
            A, B,
            O, O + D * FAR
        )
        dir_vec = p_ray - p_seg
        n = numpy.linalg.norm(dir_vec)
        if n &gt; 1e-8:
            p_col = p_seg + dir_vec * (r / n)
        else:
            # Луч параллелен оси: сдвигаем вдоль любой нормали.
            normal = numpy.cross(U, numpy.array([1.0, 0.0, 0.0]))
            if numpy.linalg.norm(normal) &lt; 1e-8:
                normal = numpy.cross(U, numpy.array([0.0, 1.0, 0.0]))
            normal = normal / numpy.linalg.norm(normal)
            p_col = p_seg + normal * r
        return p_col, p_ray, numpy.linalg.norm(p_col - p_ray)
    
    def __init__(self, a: numpy.ndarray, b: numpy.ndarray, radius: float):
        self.a = a
        self.b = b
        self.radius = radius

    def transform_by(self, transform: 'Pose3'):
        &quot;&quot;&quot;Return a new CapsuleCollider transformed by the given Pose3.&quot;&quot;&quot;
        new_a = transform.transform_point(self.a)
        new_b = transform.transform_point(self.b)
        return CapsuleCollider(new_a, new_b, self.radius)
    
    def closest_to_capsule(self, other: &quot;CapsuleCollider&quot;):
        &quot;&quot;&quot;Return the closest points and distance between this capsule and another capsule.&quot;&quot;&quot;
        p_near, q_near, dist = closest_points_between_capsules(
            self.a, self.b, self.radius,
            other.a, other.b, other.radius)
        return p_near, q_near, dist

    def closest_to_sphere(self, other: &quot;SphereCollider&quot;):
        &quot;&quot;&quot;Return the closest points and distance between this capsule and a sphere.&quot;&quot;&quot;
        p_near, q_near, dist = closest_points_between_capsule_and_sphere(
            self.a, self.b, self.radius,
            other.center, other.radius)
        return p_near, q_near, dist

    def closest_to_union_collider(self, other: &quot;UnionCollider&quot;):
        &quot;&quot;&quot;Return the closest points and distance between this capsule and a union collider.&quot;&quot;&quot;
        a,b,c = other.closest_to_collider(self)
        return b,a,c

    def closest_to_collider(self, other: &quot;Collider&quot;):
        &quot;&quot;&quot;Return the closest points and distance between this collider and another collider.&quot;&quot;&quot;

        from .sphere import SphereCollider
        from .union_collider import UnionCollider

        if isinstance(other, CapsuleCollider):
            return self.closest_to_capsule(other)
        elif isinstance(other, SphereCollider):
            return other.closest_to_sphere(self)
        elif isinstance(other, UnionCollider):
            return self.closest_to_union_collider(other)
        else:
            raise NotImplementedError(f&quot;closest_to_collider not implemented for {type(other)}&quot;)

    def distance(self, other: &quot;Collider&quot;) -&gt; float:
        &quot;&quot;&quot;Return the distance between this collider and another collider.&quot;&quot;&quot;
        _, _, dist = self.closest_to_collider(other)
        return dist

</code></pre>
</body>
</html>
