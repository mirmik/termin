from __future__ import annotations

from termin.colliders import (
    Collider, SphereCollider, BoxCollider, CapsuleCollider, AttachedCollider
)
from termin.geombase import Vec3
from termin.visualization.core.python_component import PythonComponent
from termin.editor.inspect_field import InspectField


class ColliderComponent(PythonComponent):
    """
    Компонент, навешиваемый на Entity.
    Оборачивает коллайдер в AttachedCollider, который следует за entity.transform.
    """

    inspect_fields = {
        "enabled": InspectField(
            path="enabled",
            label="Enabled",
            kind="bool",
        ),
        "collider_type": InspectField(
            path="collider_type",
            label="Type",
            kind="enum",
            choices=[("Box", "Box"), ("Sphere", "Sphere"), ("Capsule", "Capsule")],
            setter=lambda self, v: self._set_collider_type(v),
        ),
        # Box parameters
        "box_size": InspectField(
            path="box_size",
            label="Size",
            kind="vec3",
            setter=lambda self, v: self._set_box_size(v),
        ),
        # Sphere parameters
        "sphere_radius": InspectField(
            path="sphere_radius",
            label="Radius",
            kind="float",
            min=0.01,
            setter=lambda self, v: self._set_sphere_radius(v),
        ),
        # Capsule parameters
        "capsule_height": InspectField(
            path="capsule_height",
            label="Height",
            kind="float",
            min=0.0,
            setter=lambda self, v: self._set_capsule_height(v),
        ),
        "capsule_radius": InspectField(
            path="capsule_radius",
            label="Radius",
            kind="float",
            min=0.01,
            setter=lambda self, v: self._set_capsule_radius(v),
        ),
    }

    def __init__(self, collider: Collider | None = None):
        super().__init__(enabled=True)

        # Type and parameters
        self.collider_type: str = "Box"
        self.box_size: tuple = (1.0, 1.0, 1.0)
        self.sphere_radius: float = 0.5
        self.capsule_height: float = 1.0
        self.capsule_radius: float = 0.25

        # If a collider was passed, extract its type and parameters
        if collider is not None:
            self._extract_collider_params(collider)
            self._source_collider = collider
        else:
            self._source_collider = self._create_collider()

        self._attached = None
        self._scene = None  # Reference to scene for CollisionWorld access

    def _extract_collider_params(self, collider: Collider):
        """Extract type and parameters from an existing collider."""
        if isinstance(collider, BoxCollider):
            self.collider_type = "Box"
            hs = collider.half_size
            self.box_size = (hs.x * 2, hs.y * 2, hs.z * 2)
        elif isinstance(collider, SphereCollider):
            self.collider_type = "Sphere"
            self.sphere_radius = float(collider.radius)
        elif isinstance(collider, CapsuleCollider):
            self.collider_type = "Capsule"
            # half_height is the half-length of the axis (not including caps)
            self.capsule_height = float(collider.half_height * 2)
            self.capsule_radius = float(collider.radius)

    def _create_collider(self) -> Collider:
        """Create a collider based on current type and parameters."""
        if self.collider_type == "Box":
            half = Vec3(self.box_size[0] / 2, self.box_size[1] / 2, self.box_size[2] / 2)
            return BoxCollider(half)
        elif self.collider_type == "Sphere":
            return SphereCollider(self.sphere_radius)
        elif self.collider_type == "Capsule":
            half_height = self.capsule_height / 2.0
            return CapsuleCollider(half_height, self.capsule_radius)
        else:
            return BoxCollider(Vec3(0.5, 0.5, 0.5))

    def _rebuild_collider(self):
        """Rebuild collider after parameter change."""
        self._source_collider = self._create_collider()
        self._rebuild_attached()

    def _rebuild_attached(self):
        """Rebuild AttachedCollider with current collider and transform."""
        # Remove old attached from collision world
        if self._attached is not None and self._scene is not None:
            self._scene.collision_world.remove(self._attached)

        if self._source_collider is not None and self.entity is not None:
            self._attached = AttachedCollider(self._source_collider, self.entity.transform)
            # Add new attached to collision world
            if self._scene is not None:
                self._scene.collision_world.add(self._attached)

    def _set_collider_type(self, value: str):
        if value != self.collider_type:
            self.collider_type = value
            self._rebuild_collider()

    def _set_box_size(self, value):
        self.box_size = tuple(value)
        if self.collider_type == "Box":
            self._rebuild_collider()

    def _set_sphere_radius(self, value: float):
        self.sphere_radius = value
        if self.collider_type == "Sphere":
            self._rebuild_collider()

    def _set_capsule_height(self, value: float):
        self.capsule_height = value
        if self.collider_type == "Capsule":
            self._rebuild_collider()

    def _set_capsule_radius(self, value: float):
        self.capsule_radius = value
        if self.collider_type == "Capsule":
            self._rebuild_collider()

    def on_added(self, scene):
        super().on_added(scene)
        self._scene = scene
        self._rebuild_attached()

    def on_removed(self):
        """Remove collider from collision world when component is removed."""
        if self._attached is not None and self._scene is not None:
            self._scene.collision_world.remove(self._attached)
        self._scene = None
        super().on_removed()

    @property
    def attached(self) -> AttachedCollider | None:
        """Get the AttachedCollider."""
        return self._attached

    @property
    def collider(self) -> Collider:
        """Return the source collider (Box, Sphere, Capsule)."""
        return self._source_collider
