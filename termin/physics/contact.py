"""Contact detection and constraint solving."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from termin.physics.rigid_body import RigidBody


@dataclass
class Contact:
    """
    A contact point between two rigid bodies.

    Attributes:
        body_a: First body (can be None for world/ground contact)
        body_b: Second body
        point: Contact point in world coordinates
        normal: Contact normal (pointing from A to B, or up for ground)
        penetration: Penetration depth (positive = overlapping)
    """
    body_a: RigidBody | None
    body_b: RigidBody
    point: np.ndarray
    normal: np.ndarray
    penetration: float

    # For warm starting (accumulated impulse from previous frame)
    accumulated_normal_impulse: float = 0.0
    accumulated_tangent_impulse: np.ndarray = None

    def __post_init__(self):
        if self.accumulated_tangent_impulse is None:
            self.accumulated_tangent_impulse = np.zeros(2, dtype=np.float64)


class ContactConstraint:
    """
    Solver for contact constraints using Sequential Impulses.
    """

    def __init__(
        self,
        contact: Contact,
        restitution: float = 0.3,
        friction: float = 0.5,
        baumgarte: float = 0.2,
        slop: float = 0.005,
    ):
        self.contact = contact
        self.restitution = restitution
        self.friction = friction
        self.baumgarte = baumgarte
        self.slop = slop

        # Precompute constraint data
        self._precompute()

        # Store initial closing velocity for restitution (computed once)
        self._initial_v_n = None

    def _precompute(self):
        """Precompute effective mass and bias."""
        c = self.contact
        n = c.normal

        # Compute effective mass for normal impulse
        # w = 1/m_a + 1/m_b + n·(I_a^{-1} @ (r_a×n))×r_a + n·(I_b^{-1} @ (r_b×n))×r_b

        w = 0.0

        if c.body_a is not None and not c.body_a.is_static:
            r_a = c.point - c.body_a.position
            rxn_a = np.cross(r_a, n)
            w += c.body_a.inv_mass
            w += np.dot(n, np.cross(c.body_a.world_inertia_inv() @ rxn_a, r_a))

        if c.body_b is not None and not c.body_b.is_static:
            r_b = c.point - c.body_b.position
            rxn_b = np.cross(r_b, n)
            w += c.body_b.inv_mass
            w += np.dot(n, np.cross(c.body_b.world_inertia_inv() @ rxn_b, r_b))

        self.effective_mass_normal = 1.0 / w if w > 1e-10 else 0.0

        # Compute tangent directions for friction
        # Find two orthogonal tangent vectors
        if abs(n[0]) < 0.9:
            t1 = np.cross(n, np.array([1, 0, 0], dtype=np.float64))
        else:
            t1 = np.cross(n, np.array([0, 1, 0], dtype=np.float64))
        t1 = t1 / np.linalg.norm(t1)
        t2 = np.cross(n, t1)

        self.tangent1 = t1
        self.tangent2 = t2

        # Effective mass for tangent impulses
        self.effective_mass_tangent1 = self._compute_effective_mass(t1)
        self.effective_mass_tangent2 = self._compute_effective_mass(t2)

    def _compute_effective_mass(self, direction: np.ndarray) -> float:
        """Compute effective mass in a given direction."""
        c = self.contact
        w = 0.0

        if c.body_a is not None and not c.body_a.is_static:
            r_a = c.point - c.body_a.position
            rxd_a = np.cross(r_a, direction)
            w += c.body_a.inv_mass
            w += np.dot(direction, np.cross(c.body_a.world_inertia_inv() @ rxd_a, r_a))

        if c.body_b is not None and not c.body_b.is_static:
            r_b = c.point - c.body_b.position
            rxd_b = np.cross(r_b, direction)
            w += c.body_b.inv_mass
            w += np.dot(direction, np.cross(c.body_b.world_inertia_inv() @ rxd_b, r_b))

        return 1.0 / w if w > 1e-10 else 0.0

    def relative_velocity(self) -> np.ndarray:
        """Compute relative velocity at contact point (v_b - v_a)."""
        c = self.contact

        v_b = np.zeros(3, dtype=np.float64)
        if c.body_b is not None:
            v_b = c.body_b.point_velocity(c.point)

        v_a = np.zeros(3, dtype=np.float64)
        if c.body_a is not None:
            v_a = c.body_a.point_velocity(c.point)

        return v_b - v_a

    def solve_normal(self, dt: float):
        """Solve normal (non-penetration) constraint."""
        c = self.contact
        n = c.normal

        # Relative velocity along normal (positive = separating, negative = closing)
        v_rel = self.relative_velocity()
        v_n = np.dot(v_rel, n)

        # Store initial closing velocity for restitution (only once)
        if self._initial_v_n is None:
            self._initial_v_n = v_n

        # Target velocity: we want v_n >= 0 (non-penetrating)
        # For resting contact: v_n = 0
        # For bouncing contact: v_n = -restitution * initial_v_n

        target_v_n = 0.0

        # Apply restitution only on first impact (when initially closing fast)
        if self._initial_v_n < -1.0:
            target_v_n = -self.restitution * self._initial_v_n

        # Compute impulse to reach target velocity
        # impulse = m_eff * (target_v_n - v_n)
        impulse = self.effective_mass_normal * (target_v_n - v_n)

        # Clamp accumulated impulse (contact can only push, not pull)
        old_accumulated = c.accumulated_normal_impulse
        c.accumulated_normal_impulse = max(0.0, old_accumulated + impulse)
        impulse = c.accumulated_normal_impulse - old_accumulated

        # Apply impulse
        impulse_vec = n * impulse
        self._apply_impulse(impulse_vec)

    def solve_friction(self):
        """Solve tangential (friction) constraints."""
        c = self.contact

        # Maximum friction impulse (Coulomb friction)
        max_friction = self.friction * c.accumulated_normal_impulse

        # Solve tangent1
        v_rel = self.relative_velocity()
        v_t1 = np.dot(v_rel, self.tangent1)
        impulse_t1 = self.effective_mass_tangent1 * (-v_t1)

        old_t1 = c.accumulated_tangent_impulse[0]
        c.accumulated_tangent_impulse[0] = np.clip(
            old_t1 + impulse_t1, -max_friction, max_friction
        )
        impulse_t1 = c.accumulated_tangent_impulse[0] - old_t1

        # Solve tangent2
        v_rel = self.relative_velocity()
        v_t2 = np.dot(v_rel, self.tangent2)
        impulse_t2 = self.effective_mass_tangent2 * (-v_t2)

        old_t2 = c.accumulated_tangent_impulse[1]
        c.accumulated_tangent_impulse[1] = np.clip(
            old_t2 + impulse_t2, -max_friction, max_friction
        )
        impulse_t2 = c.accumulated_tangent_impulse[1] - old_t2

        # Apply friction impulses
        impulse_vec = self.tangent1 * impulse_t1 + self.tangent2 * impulse_t2
        self._apply_impulse(impulse_vec)

    def _apply_impulse(self, impulse: np.ndarray):
        """Apply impulse to both bodies."""
        c = self.contact

        if c.body_a is not None and not c.body_a.is_static:
            c.body_a.apply_impulse(-impulse, c.point)

        if c.body_b is not None and not c.body_b.is_static:
            c.body_b.apply_impulse(impulse, c.point)
