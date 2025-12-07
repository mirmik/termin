"""Rigid body for physics simulation."""

from __future__ import annotations

import numpy as np
from termin.geombase.pose3 import Pose3
from termin.geombase.screw import Screw3
from termin.colliders.collider import Collider


class RigidBody:
    """
    A rigid body with mass, inertia, pose, and velocity.

    - Pose: Pose3 (position + orientation)
    - Velocity: Screw3 (ang=omega, lin=v) in world frame
    - Wrench: Screw3 (ang=torque, lin=force) accumulated per step
    """

    def __init__(
        self,
        mass: float = 1.0,
        inertia: np.ndarray | None = None,
        pose: Pose3 | None = None,
        collider: Collider | None = None,
        is_static: bool = False,
    ):
        self.mass = mass

        # Inertia tensor in body frame (3x3)
        if inertia is None:
            # Default: unit cube inertia
            self.inertia = np.eye(3, dtype=np.float64) * (mass / 6.0)
        else:
            self.inertia = np.asarray(inertia, dtype=np.float64)

        # Inverse inertia (precomputed)
        if is_static or mass <= 0:
            self.inv_mass = 0.0
            self.inv_inertia = np.zeros((3, 3), dtype=np.float64)
        else:
            self.inv_mass = 1.0 / mass
            self.inv_inertia = np.linalg.inv(self.inertia)

        # Pose (position + orientation)
        if pose is None:
            self.pose = Pose3.identity()
        else:
            self.pose = pose

        # Velocity as Screw3 (ang=omega, lin=v) in world frame
        self.velocity = Screw3(
            ang=np.zeros(3, dtype=np.float64),
            lin=np.zeros(3, dtype=np.float64),
        )

        # Accumulated wrench (ang=torque, lin=force) - reset each step
        self.wrench = Screw3(
            ang=np.zeros(3, dtype=np.float64),
            lin=np.zeros(3, dtype=np.float64),
        )

        # Collider (in local frame)
        self.collider = collider

        # Static bodies don't move
        self.is_static = is_static

    @property
    def position(self) -> np.ndarray:
        """Position (center of mass) in world frame."""
        return self.pose.lin

    @position.setter
    def position(self, p: np.ndarray):
        self.pose = Pose3(ang=self.pose.ang.copy(), lin=np.asarray(p, dtype=np.float64))

    @property
    def rotation(self) -> np.ndarray:
        """Rotation matrix (body to world)."""
        return self.pose.rotation_matrix()

    @property
    def omega(self) -> np.ndarray:
        """Angular velocity in world frame."""
        return self.velocity.ang

    @omega.setter
    def omega(self, w: np.ndarray):
        self.velocity = Screw3(ang=np.asarray(w, dtype=np.float64), lin=self.velocity.lin)

    @property
    def linear_velocity(self) -> np.ndarray:
        """Linear velocity in world frame."""
        return self.velocity.lin

    @linear_velocity.setter
    def linear_velocity(self, v: np.ndarray):
        self.velocity = Screw3(ang=self.velocity.ang, lin=np.asarray(v, dtype=np.float64))

    def world_inertia_inv(self) -> np.ndarray:
        """Inverse inertia tensor in world frame."""
        R = self.rotation
        return R @ self.inv_inertia @ R.T

    def apply_wrench(self, w: Screw3):
        """Apply wrench (ang=torque, lin=force) at center of mass."""
        self.wrench = Screw3(
            ang=self.wrench.ang + w.ang,
            lin=self.wrench.lin + w.lin,
        )

    def apply_force(self, force: np.ndarray, point: np.ndarray | None = None):
        """
        Apply force at a point (world coordinates).
        If point is None, applies at center of mass (no torque).
        """
        torque = np.zeros(3, dtype=np.float64)
        if point is not None:
            r = point - self.position
            torque = np.cross(r, force)

        self.wrench = Screw3(
            ang=self.wrench.ang + torque,
            lin=self.wrench.lin + force,
        )

    def apply_impulse(self, impulse: np.ndarray, point: np.ndarray):
        """
        Apply linear impulse at a specific point.
        Creates both linear and angular velocity change.
        """
        if self.is_static:
            return

        new_lin = self.velocity.lin + impulse * self.inv_mass

        r = point - self.position
        angular_impulse = np.cross(r, impulse)
        new_ang = self.velocity.ang + self.world_inertia_inv() @ angular_impulse

        self.velocity = Screw3(ang=new_ang, lin=new_lin)

    def point_velocity(self, point: np.ndarray) -> np.ndarray:
        """Velocity of a point on the body (world coordinates)."""
        r = point - self.position
        return self.velocity.lin + np.cross(self.velocity.ang, r)

    def integrate_forces(self, dt: float, gravity: np.ndarray):
        """Integrate forces to update velocities."""
        if self.is_static:
            return

        # Apply gravity
        total_force = self.wrench.lin + self.mass * gravity
        total_torque = self.wrench.ang

        # Linear: v += (F/m) * dt
        new_lin = self.velocity.lin + (total_force * self.inv_mass) * dt

        # Angular: omega += I^{-1} * torque * dt
        new_ang = self.velocity.ang + (self.world_inertia_inv() @ total_torque) * dt

        self.velocity = Screw3(ang=new_ang, lin=new_lin)

        # Clear accumulated wrench
        self.wrench = Screw3(
            ang=np.zeros(3, dtype=np.float64),
            lin=np.zeros(3, dtype=np.float64),
        )

    def integrate_positions(self, dt: float):
        """Integrate velocities to update pose."""
        if self.is_static:
            return

        # Linear: x += v * dt
        new_position = self.position + self.velocity.lin * dt

        # Angular: use Screw3.to_pose() for exponential map
        omega_dt = Screw3(ang=self.velocity.ang * dt, lin=np.zeros(3))
        delta_pose = omega_dt.to_pose()

        # New orientation: delta_pose * current_pose (rotation part)
        new_pose = Pose3(
            ang=_quat_multiply(delta_pose.ang, self.pose.ang),
            lin=new_position,
        )
        self.pose = new_pose

    def world_collider(self) -> Collider | None:
        """Get collider transformed to world frame."""
        if self.collider is None:
            return None
        return self.collider.transform_by(self.pose)

    @staticmethod
    def create_box(
        size: np.ndarray | tuple = (1, 1, 1),
        mass: float = 1.0,
        pose: Pose3 | None = None,
        is_static: bool = False,
    ) -> RigidBody:
        """Create a box rigid body with correct inertia."""
        from termin.colliders.box import BoxCollider

        size = np.asarray(size, dtype=np.float64)
        sx, sy, sz = size

        # Box inertia tensor (around center of mass)
        Ixx = (mass / 12.0) * (sy**2 + sz**2)
        Iyy = (mass / 12.0) * (sx**2 + sz**2)
        Izz = (mass / 12.0) * (sx**2 + sy**2)
        inertia = np.diag([Ixx, Iyy, Izz])

        collider = BoxCollider(
            center=np.zeros(3, dtype=np.float32),
            size=size.astype(np.float32),
        )

        return RigidBody(
            mass=mass,
            inertia=inertia,
            pose=pose,
            collider=collider,
            is_static=is_static,
        )

    @staticmethod
    def create_sphere(
        radius: float = 0.5,
        mass: float = 1.0,
        pose: Pose3 | None = None,
        is_static: bool = False,
    ) -> RigidBody:
        """Create a sphere rigid body with correct inertia."""
        from termin.colliders.sphere import SphereCollider

        # Sphere inertia: I = (2/5) * m * r^2
        I = (2.0 / 5.0) * mass * radius**2
        inertia = np.diag([I, I, I])

        collider = SphereCollider(
            center=np.zeros(3, dtype=np.float32),
            radius=radius,
        )

        return RigidBody(
            mass=mass,
            inertia=inertia,
            pose=pose,
            collider=collider,
            is_static=is_static,
        )

    @staticmethod
    def create_static_ground(
        size: tuple = (100, 100, 1),
        height: float = 0.0,
    ) -> RigidBody:
        """Create a static ground plane (large flat box)."""
        pose = Pose3.identity().with_translation(np.array([0, 0, height - size[2] / 2]))

        return RigidBody.create_box(
            size=size,
            mass=0.0,
            pose=pose,
            is_static=True,
        )


def _quat_multiply(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
    """Multiply two quaternions (x, y, z, w format)."""
    x1, y1, z1, w1 = q1
    x2, y2, z2, w2 = q2
    return np.array([
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2,
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
    ], dtype=np.float64)
