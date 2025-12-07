"""RigidBody component for visualization entities."""

from __future__ import annotations

from typing import TYPE_CHECKING
import numpy as np

from termin.visualization.core.entity import Component
from termin.physics.rigid_body import RigidBody
from termin.geombase.pose3 import Pose3

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene


class RigidBodyComponent(Component):
    """
    Component that binds a RigidBody to an Entity.

    Synchronizes physics pose with entity transform.
    """

    def __init__(
        self,
        mass: float = 1.0,
        is_static: bool = False,
        restitution: float = 0.3,
        friction: float = 0.5,
    ):
        super().__init__(enabled=True)
        self.mass = mass
        self.is_static = is_static
        self.restitution = restitution
        self.friction = friction

        # Will be created in start()
        self._rigid_body: RigidBody | None = None

    @property
    def rigid_body(self) -> RigidBody | None:
        return self._rigid_body

    def start(self, scene: "Scene"):
        super().start(scene)

        if self.entity is None:
            return

        # Get initial pose from entity transform
        initial_pose = self.entity.transform.global_pose()

        # Determine collider from entity's mesh (if any)
        collider = self._create_collider_from_entity()

        # Compute inertia based on collider type
        inertia = self._compute_inertia(collider)

        self._rigid_body = RigidBody(
            mass=self.mass if not self.is_static else 0.0,
            inertia=inertia,
            pose=initial_pose,
            collider=collider,
            is_static=self.is_static,
        )

    def _create_collider_from_entity(self):
        """Try to create a collider based on entity's mesh."""
        if self.entity is None:
            return None

        # Check for existing collider component
        from termin.colliders.collider_component import ColliderComponent
        collider_comp = self.entity.get_component(ColliderComponent)
        if collider_comp is not None:
            return collider_comp.collider

        # Try to create from mesh renderer
        from termin.visualization.render.components.mesh_renderer import MeshRenderer
        mesh_renderer = self.entity.get_component(MeshRenderer)
        if mesh_renderer is not None and mesh_renderer.mesh is not None:
            # Approximate with box collider from mesh bounds
            mesh = mesh_renderer.mesh
            if hasattr(mesh, 'get_bounds'):
                bounds = mesh.get_bounds()
                from termin.colliders.box import BoxCollider
                size = bounds.max_point - bounds.min_point
                center = (bounds.max_point + bounds.min_point) / 2
                return BoxCollider(center=center, size=size)

        # Default: unit box
        from termin.colliders.box import BoxCollider
        return BoxCollider(
            center=np.zeros(3, dtype=np.float32),
            size=np.ones(3, dtype=np.float32),
        )

    def _compute_inertia(self, collider) -> np.ndarray:
        """Compute inertia tensor based on collider shape."""
        from termin.colliders.box import BoxCollider
        from termin.colliders.sphere import SphereCollider

        m = self.mass

        if isinstance(collider, BoxCollider):
            sx, sy, sz = collider.size
            Ixx = (m / 12.0) * (sy**2 + sz**2)
            Iyy = (m / 12.0) * (sx**2 + sz**2)
            Izz = (m / 12.0) * (sx**2 + sy**2)
            return np.diag([Ixx, Iyy, Izz])

        elif isinstance(collider, SphereCollider):
            r = collider.radius
            I = (2.0 / 5.0) * m * r**2
            return np.diag([I, I, I])

        else:
            # Default: unit sphere inertia
            return np.eye(3) * (m / 6.0)

    def update(self, dt: float):
        """Sync entity transform from physics body."""
        if self._rigid_body is None or self.entity is None:
            return

        # Copy pose from physics to entity
        self.entity.transform.relocate(self._rigid_body.pose)

    def sync_to_physics(self):
        """Sync physics body from entity transform (for editor manipulation)."""
        if self._rigid_body is None or self.entity is None:
            return

        self._rigid_body.pose = self.entity.transform.global_pose()
        # Reset velocities when teleported
        from termin.geombase.screw import Screw3
        self._rigid_body.velocity = Screw3(
            ang=np.zeros(3, dtype=np.float64),
            lin=np.zeros(3, dtype=np.float64),
        )

    def apply_force(self, force: np.ndarray, point: np.ndarray | None = None):
        """Apply force to the rigid body."""
        if self._rigid_body is not None:
            self._rigid_body.apply_force(force, point)

    def apply_impulse(self, impulse: np.ndarray, point: np.ndarray):
        """Apply impulse to the rigid body."""
        if self._rigid_body is not None:
            self._rigid_body.apply_impulse(impulse, point)
