"""Physics world simulation."""

from __future__ import annotations

from typing import List, Callable
import numpy as np

from termin.physics.rigid_body import RigidBody
from termin.physics.contact import Contact, ContactConstraint


class PhysicsWorld:
    """
    Physics simulation world.

    Handles rigid body dynamics with collision detection and response
    using Sequential Impulses.
    """

    def __init__(
        self,
        gravity: np.ndarray | None = None,
        iterations: int = 10,
        restitution: float = 0.3,
        friction: float = 0.5,
    ):
        if gravity is None:
            self.gravity = np.array([0, 0, -9.81], dtype=np.float64)
        else:
            self.gravity = np.asarray(gravity, dtype=np.float64)

        self.iterations = iterations
        self.restitution = restitution
        self.friction = friction

        self.bodies: List[RigidBody] = []
        self._contact_constraints: List[ContactConstraint] = []

        # Ground plane (z = 0 by default)
        self.ground_height = 0.0
        self.ground_enabled = True

    def add_body(self, body: RigidBody) -> RigidBody:
        """Add a rigid body to the world."""
        self.bodies.append(body)
        return body

    def remove_body(self, body: RigidBody):
        """Remove a rigid body from the world."""
        if body in self.bodies:
            self.bodies.remove(body)

    def step(self, dt: float):
        """
        Advance simulation by dt seconds.

        Uses semi-implicit Euler with speculative contacts:
        1. Apply forces → update velocities
        2. Integrate positions (tentative)
        3. Detect collisions at new positions
        4. Solve velocity constraints (Sequential Impulses)
        5. Position correction
        """
        # 1. Integrate forces (gravity, external forces)
        for body in self.bodies:
            body.integrate_forces(dt, self.gravity)

        # 2. Integrate positions first (tentative)
        for body in self.bodies:
            body.integrate_positions(dt)

        # 3. Collision detection at new positions
        contacts = self._detect_collisions()

        # 4. Create contact constraints
        self._contact_constraints = [
            ContactConstraint(
                contact=c,
                restitution=self.restitution,
                friction=self.friction,
            )
            for c in contacts
        ]

        # 5. Velocity solve (Sequential Impulses)
        for _ in range(self.iterations):
            for constraint in self._contact_constraints:
                constraint.solve_normal(dt)
                constraint.solve_friction()

        # 6. Position correction (push bodies apart)
        self._solve_position_constraints()

    def _detect_collisions(self) -> List[Contact]:
        """Detect collisions between all bodies and ground."""
        contacts = []

        # Ground collisions
        if self.ground_enabled:
            for body in self.bodies:
                if body.is_static:
                    continue

                ground_contacts = self._detect_ground_collision(body)
                contacts.extend(ground_contacts)

        # Body-body collisions
        for i, body_a in enumerate(self.bodies):
            for body_b in self.bodies[i + 1:]:
                if body_a.is_static and body_b.is_static:
                    continue

                pair_contacts = self._detect_body_collision(body_a, body_b)
                contacts.extend(pair_contacts)

        return contacts

    def _detect_ground_collision(self, body: RigidBody) -> List[Contact]:
        """Detect collision between body and ground plane."""
        contacts = []

        collider = body.world_collider()
        if collider is None:
            # Simple sphere approximation for bodies without collider
            z = body.position[2]
            if z < self.ground_height:
                contacts.append(Contact(
                    body_a=None,
                    body_b=body,
                    point=np.array([body.position[0], body.position[1], self.ground_height]),
                    normal=np.array([0, 0, 1], dtype=np.float64),
                    penetration=self.ground_height - z,
                ))
            return contacts

        # Use collider for collision detection
        from termin.colliders.box import BoxCollider
        from termin.colliders.sphere import SphereCollider

        if isinstance(collider, SphereCollider):
            # Sphere vs ground
            center = collider.center
            radius = collider.radius
            z = center[2]

            if z - radius < self.ground_height:
                contact_point = np.array([center[0], center[1], self.ground_height])
                penetration = self.ground_height - (z - radius)
                contacts.append(Contact(
                    body_a=None,
                    body_b=body,
                    point=contact_point,
                    normal=np.array([0, 0, 1], dtype=np.float64),
                    penetration=penetration,
                ))

        elif isinstance(collider, BoxCollider):
            # Box vs ground - check all 8 corners
            aabb = collider.local_aabb()
            corners_local = [
                np.array([aabb.min_point[0], aabb.min_point[1], aabb.min_point[2]]),
                np.array([aabb.max_point[0], aabb.min_point[1], aabb.min_point[2]]),
                np.array([aabb.min_point[0], aabb.max_point[1], aabb.min_point[2]]),
                np.array([aabb.max_point[0], aabb.max_point[1], aabb.min_point[2]]),
                np.array([aabb.min_point[0], aabb.min_point[1], aabb.max_point[2]]),
                np.array([aabb.max_point[0], aabb.min_point[1], aabb.max_point[2]]),
                np.array([aabb.min_point[0], aabb.max_point[1], aabb.max_point[2]]),
                np.array([aabb.max_point[0], aabb.max_point[1], aabb.max_point[2]]),
            ]

            for corner_local in corners_local:
                corner_world = collider.pose.transform_point(corner_local)
                z = corner_world[2]

                if z < self.ground_height:
                    contact_point = np.array([
                        corner_world[0],
                        corner_world[1],
                        self.ground_height,
                    ], dtype=np.float64)
                    penetration = self.ground_height - z

                    contacts.append(Contact(
                        body_a=None,
                        body_b=body,
                        point=contact_point,
                        normal=np.array([0, 0, 1], dtype=np.float64),
                        penetration=penetration,
                    ))

        return contacts

    def _detect_body_collision(
        self, body_a: RigidBody, body_b: RigidBody
    ) -> List[Contact]:
        """Detect collision between two bodies."""
        contacts = []

        collider_a = body_a.world_collider()
        collider_b = body_b.world_collider()

        if collider_a is None or collider_b is None:
            return contacts

        # Use closest_to_collider for collision detection
        try:
            p_a, p_b, distance = collider_a.closest_to_collider(collider_b)

            # Negative distance means penetration (from SAT)
            if distance <= 0.01:  # Contact threshold
                if distance < 0:
                    # Penetrating - for Box-Box SAT:
                    # p_a = contact normal (pointing from A to B)
                    # p_b = contact point
                    penetration = -distance
                    normal = np.asarray(p_a, dtype=np.float64)
                    contact_point = np.asarray(p_b, dtype=np.float64)
                else:
                    # Close but not penetrating
                    diff = p_b - p_a
                    dist = np.linalg.norm(diff)
                    if dist > 1e-8:
                        normal = diff / dist
                    else:
                        normal = np.array([0, 0, 1], dtype=np.float64)
                    contact_point = (p_a + p_b) / 2
                    penetration = max(0, 0.01 - distance)

                contacts.append(Contact(
                    body_a=body_a,
                    body_b=body_b,
                    point=contact_point,
                    normal=normal,
                    penetration=penetration,
                ))
        except NotImplementedError:
            # Collision detection not implemented for this pair
            pass

        return contacts

    def ray_cast(
        self,
        origin: np.ndarray,
        direction: np.ndarray,
        max_distance: float = 1000.0,
    ) -> tuple[RigidBody | None, np.ndarray | None, float]:
        """
        Cast a ray and return the first hit body.

        Returns:
            (body, hit_point, distance) or (None, None, inf) if no hit
        """
        from termin.geombase.ray import Ray3

        ray = Ray3(origin, direction)
        best_body = None
        best_point = None
        best_dist = max_distance

        for body in self.bodies:
            collider = body.world_collider()
            if collider is None:
                continue

            try:
                p_col, p_ray, dist = collider.closest_to_ray(ray)
                t = np.dot(p_ray - origin, direction)

                if 0 < t < best_dist and dist < 0.01:
                    best_dist = t
                    best_body = body
                    best_point = p_col
            except (NotImplementedError, AttributeError):
                pass

        return best_body, best_point, best_dist

    def _solve_position_constraints(self):
        """
        Direct position correction to resolve penetration.

        This is a simple approach: push bodies apart along contact normal
        proportionally to penetration depth.
        """
        # Re-detect collisions after position integration
        contacts = self._detect_collisions()

        for contact in contacts:
            if contact.penetration <= 0.001:
                continue

            n = contact.normal
            correction = contact.penetration * 0.8  # 80% correction

            if contact.body_a is None:
                # Ground contact - only move body_b
                if not contact.body_b.is_static:
                    contact.body_b.position = contact.body_b.position + n * correction
            else:
                # Body-body contact
                total_inv_mass = 0.0
                if not contact.body_a.is_static:
                    total_inv_mass += contact.body_a.inv_mass
                if not contact.body_b.is_static:
                    total_inv_mass += contact.body_b.inv_mass

                if total_inv_mass > 1e-10:
                    if not contact.body_a.is_static:
                        ratio_a = contact.body_a.inv_mass / total_inv_mass
                        contact.body_a.position = contact.body_a.position - n * correction * ratio_a
                    if not contact.body_b.is_static:
                        ratio_b = contact.body_b.inv_mass / total_inv_mass
                        contact.body_b.position = contact.body_b.position + n * correction * ratio_b
