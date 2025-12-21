from termin.colliders.collider import Collider
import numpy

class UnionCollider(Collider):
    def closest_to_ray(self, ray: "Ray3"):
        min_dist = float("inf")
        best_p = None
        best_q = None

        for col in self.colliders:
            p, q, d = col.closest_to_ray(ray)
            if d < min_dist:
                min_dist = d
                best_p = p
                best_q = q

        return best_p, best_q, min_dist
    def __init__(self, colliders):
        self.colliders = colliders

    def transform_by(self, transform: 'Pose3'):
        """Return a new UnionCollider transformed by the given Transform3."""
        transformed_colliders = [collider.transform_by(transform) for collider in self.colliders]
        return UnionCollider(transformed_colliders)

    def closest_to_collider(self, other: "Collider"):
        """Return the closest points and distance between this union collider and another collider."""
        min_dist = float('inf')
        closest_p = None
        closest_q = None

        # If other is also a UnionCollider, iterate over its colliders too
        if isinstance(other, UnionCollider):
            other_colliders = other.colliders
        else:
            other_colliders = [other]

        for collider in self.colliders:
            for other_col in other_colliders:
                p_near, q_near, dist = collider.closest_to_collider(other_col)
                if dist < min_dist:
                    min_dist = dist
                    closest_p = p_near
                    closest_q = q_near

        return closest_p, closest_q, min_dist
