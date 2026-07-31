"""RigidBodyComponent canonical import path."""

from __future__ import annotations

from collections.abc import Sequence
from termin.scene import PythonComponent
from termin.physics._physics_native import (
    PhysicsWorld,
    RigidBody,
    compute_mass_properties,
)
from termin.geombase import Pose3, Vec3
from termin.inspect import InspectField
from tcbase import log

from typing import TYPE_CHECKING, Optional
import math

if TYPE_CHECKING:
    from termin.scene import TcScene as Scene


class RigidBodyComponent(PythonComponent):
    """
    Компонент, связывающий RigidBody с Entity.

    Использует C++ бэкенд. Синхронизирует позу физического тела с трансформом сущности.
    """

    inspect_fields = {
        "mass": InspectField(
            path="mass",
            label="Mass",
            kind="float",
            min=0.001,
            max=10000.0,
            step=0.1,
        ),
        "is_static": InspectField(
            path="is_static",
            label="Static",
            kind="bool",
        ),
        "restitution": InspectField(
            path="restitution",
            label="Restitution",
            kind="float",
            min=0.0,
            max=1.0,
            step=0.05,
        ),
        "friction": InspectField(
            path="friction",
            label="Friction",
            kind="float",
            min=0.0,
            max=2.0,
            step=0.05,
        ),
    }

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
        self._body_index: int = -1
        self._physics_world: Optional[PhysicsWorld] = None
        self._registered_collider = None
        self._half_extents = Vec3(0.5, 0.5, 0.5)

    def start(self):
        super().start()

        if self.entity is None:
            return

        pose_and_scale = self._physics_pose_and_scale()
        if pose_and_scale is None:
            return
        _, scale = pose_and_scale
        self._half_extents = self._compute_half_extents(scale)

        scene = self.entity.scene if self.entity else None
        if scene:
            self._find_and_register_with_physics_world(scene)

    def _physics_pose_and_scale(self) -> tuple[Pose3, Vec3] | None:
        if self.entity is None:
            return None

        transform = self.entity.transform
        scale = transform.decomposed_global_scale()
        if scale is None:
            log.error(
                f"RigidBodyComponent on '{self.entity.name}' rejects an affine "
                "world transform; rigid physics requires a decomposed world basis"
            )
            return None
        if (
            not math.isfinite(scale.x)
            or not math.isfinite(scale.y)
            or not math.isfinite(scale.z)
            or scale.x <= 0.0
            or scale.y <= 0.0
            or scale.z <= 0.0
        ):
            log.error(
                f"RigidBodyComponent on '{self.entity.name}' rejects non-positive "
                f"or non-finite world scale {scale}"
            )
            return None
        return (
            Pose3(
                transform.global_rotation.copy(),
                transform.global_position.copy(),
            ),
            scale,
        )

    def _compute_half_extents(self, global_scale: Vec3) -> Vec3:
        if self.entity is None:
            return Vec3(0.5, 0.5, 0.5)

        from termin.colliders.collider_component import ColliderComponent
        from termin.colliders import BoxCollider, SphereCollider

        collider_comp = self.entity.get_component(ColliderComponent)
        if collider_comp is not None:
            collider = collider_comp.collider
            if isinstance(collider, BoxCollider):
                hs = collider.half_size
                return _componentwise_mul(hs, global_scale)
            if isinstance(collider, SphereCollider):
                r = collider.radius
                uniform_scale = min(
                    global_scale.x,
                    global_scale.y,
                    global_scale.z,
                )
                return Vec3(
                    r * uniform_scale,
                    r * uniform_scale,
                    r * uniform_scale,
                )

        return _componentwise_mul(Vec3(0.5, 0.5, 0.5), global_scale)

    def _find_and_register_with_physics_world(self, scene: "Scene"):
        if self._body_index >= 0:
            return

        from termin.physics_components.physics_world_component import PhysicsWorldComponent

        for entity in scene.entities:
            pw_comp = entity.get_component(PhysicsWorldComponent)
            if pw_comp is not None:
                pw_comp.add_rigid_body_component(self)
                return

    def _register_with_world(self, world: PhysicsWorld):
        if self.entity is None:
            return

        if self._body_index >= 0 and self._physics_world is world:
            return

        self._physics_world = world

        pose_and_scale = self._physics_pose_and_scale()
        if pose_and_scale is None:
            self._physics_world = None
            return
        cpp_pose, scale = pose_and_scale
        self._half_extents = self._compute_half_extents(scale)

        body = self._create_body(cpp_pose, scale)
        if body is None:
            self._physics_world = None
            return
        self._body_index = world.add_body(body)
        self._ensure_collider_registered()

    def _ensure_collider_registered(self) -> bool:
        from termin.colliders.collider_component import ColliderComponent

        if (
            self.entity is None
            or self._physics_world is None
            or self._body_index < 0
        ):
            return False

        collider_comp = self.entity.get_component(ColliderComponent)
        if collider_comp is None or collider_comp.attached is None:
            return False

        collider = collider_comp.attached
        if collider is self._registered_collider:
            return True

        self._physics_world.register_collider(self._body_index, collider)
        self._registered_collider = collider
        return True

    def _create_body(self, pose: Pose3, scale: Vec3) -> RigidBody | None:
        from termin.colliders.collider_component import ColliderComponent

        collider_comp = (
            self.entity.get_component(ColliderComponent)
            if self.entity is not None
            else None
        )
        if collider_comp is None:
            sx, sy, sz = self._half_extents * 2.0
            return RigidBody.create_box(
                sx,
                sy,
                sz,
                self.mass,
                pose,
                self.is_static,
            )
        if collider_comp.collider is None:
            log.error(
                f"RigidBodyComponent on '{self.entity.name}' cannot compute mass "
                "properties because its collider geometry is unavailable"
            )
            return None

        try:
            properties = compute_mass_properties(
                collider_comp.collider,
                scale,
                self.mass,
            )
        except (RuntimeError, ValueError) as error:
            log.error(
                f"RigidBodyComponent on '{self.entity.name}' rejected "
                f"{collider_comp.collider_type} mass properties: {error}"
            )
            return None

        return RigidBody.create_with_mass_properties(
            properties,
            pose,
            self.is_static,
        )

    def _sync_from_physics(self):
        if self._body_index < 0 or self._physics_world is None or self.entity is None:
            return

        cpp_body = self._physics_world.get_body(self._body_index)
        cpp_pose = cpp_body.shape_pose()

        self.entity.transform.set_global_position(cpp_pose.lin)
        self.entity.transform.set_global_orientation(cpp_pose.ang)

    def sync_to_physics(self):
        if self._body_index < 0 or self._physics_world is None or self.entity is None:
            return

        pose_and_scale = self._physics_pose_and_scale()
        if pose_and_scale is None:
            return
        py_pose, _ = pose_and_scale
        cpp_body = self._physics_world.get_body(self._body_index)

        cpp_body.set_shape_pose(py_pose)

        cpp_body.linear_velocity = Vec3(0, 0, 0)
        cpp_body.angular_velocity = Vec3(0, 0, 0)

    def apply_impulse(self, impulse: Sequence[float], point: Optional[Sequence[float]] = None):
        if self._body_index < 0 or self._physics_world is None:
            return

        cpp_body = self._physics_world.get_body(self._body_index)
        impulse_vec = Vec3(float(impulse[0]), float(impulse[1]), float(impulse[2]))

        if point is not None:
            cpp_body.apply_impulse_at_point(
                impulse_vec,
                Vec3(float(point[0]), float(point[1]), float(point[2]))
            )
        else:
            cpp_body.apply_impulse(impulse_vec)

    @property
    def rigid_body(self):
        return None

    def update(self, dt: float):
        self._sync_from_physics()


def _componentwise_mul(a: Vec3, b: Vec3) -> Vec3:
    return Vec3(a.x * b.x, a.y * b.y, a.z * b.z)
