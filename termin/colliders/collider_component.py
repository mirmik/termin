from __future__ import annotations

import numpy as np

from termin.colliders.attached import AttachedCollider
from termin.colliders.collider import Collider
from termin.visualization.core.component import Component
from termin.editor.inspect_field import InspectField


class ColliderComponent(Component):
    """
    Компонент, навешиваемый на Entity.
    Оборачивает коллайдер в AttachedCollider, чтобы он следовал за Transform3.
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

        self.attached = None

    def _extract_collider_params(self, collider: Collider):
        """Extract type and parameters from an existing collider."""
        from termin.colliders.box import BoxCollider
        from termin.colliders.sphere import SphereCollider
        from termin.colliders.capsule import CapsuleCollider

        if isinstance(collider, BoxCollider):
            self.collider_type = "Box"
            self.box_size = tuple(collider.size)
        elif isinstance(collider, SphereCollider):
            self.collider_type = "Sphere"
            self.sphere_radius = float(collider.radius)
        elif isinstance(collider, CapsuleCollider):
            self.collider_type = "Capsule"
            # Calculate height from a and b
            a = np.asarray(collider.a)
            b = np.asarray(collider.b)
            self.capsule_height = float(np.linalg.norm(b - a))
            self.capsule_radius = float(collider.radius)

    def _create_collider(self) -> Collider:
        """Create a collider based on current type and parameters."""
        from termin.colliders.box import BoxCollider
        from termin.colliders.sphere import SphereCollider
        from termin.colliders.capsule import CapsuleCollider

        if self.collider_type == "Box":
            return BoxCollider(
                center=np.zeros(3, dtype=np.float32),
                size=np.array(self.box_size, dtype=np.float32),
            )
        elif self.collider_type == "Sphere":
            return SphereCollider(
                center=np.zeros(3, dtype=np.float32),
                radius=self.sphere_radius,
            )
        elif self.collider_type == "Capsule":
            # Capsule aligned along local Z axis
            half_height = self.capsule_height / 2.0
            return CapsuleCollider(
                a=np.array([0.0, 0.0, -half_height], dtype=np.float32),
                b=np.array([0.0, 0.0, half_height], dtype=np.float32),
                radius=self.capsule_radius,
            )
        else:
            # Fallback to box
            return BoxCollider()

    def _rebuild_collider(self):
        """Rebuild collider after parameter change."""
        self._source_collider = self._create_collider()
        # Update attached if we're in a scene
        if self.attached is not None and self.entity is not None:
            self.attached = AttachedCollider(self._source_collider, self.entity.transform)

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
        if self.entity is None:
            return
        # entity.transform всегда Transform3
        self.attached = AttachedCollider(self._source_collider, self.entity.transform)

    def get_collider(self):
        return self.attached
