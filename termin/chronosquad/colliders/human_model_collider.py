"""HumanModelCollider - automatically adds colliders to humanoid skeleton bones.

Based on ChronoSquad's HumanModelCollider.cs.
Adds capsule/sphere colliders to bones by name pattern matching.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from termin.colliders import CapsuleCollider, SphereCollider
from termin.colliders.collider_component import ColliderComponent
from termin.editor.inspect_field import InspectField
from termin.geombase import GeneralPose3, Quat, Vec3
from termin.visualization.core.python_component import PythonComponent

if TYPE_CHECKING:
    from termin.visualization import Entity


class HumanModelCollider(PythonComponent):
    """
    Component that automatically adds colliders to humanoid skeleton bones.

    Usage:
    1. Add this component to an entity with SkeletonController (or its parent)
    2. Click "Add Colliders" button in inspector
    3. Colliders will be added to bone entities matching predefined patterns
    """

    inspect_fields = {
        "scale": InspectField(
            path="scale",
            label="Scale",
            kind="float",
            min=0.1,
            max=10.0,
            step=0.1,
        ),
        "overlap_radius": InspectField(
            path="overlap_radius",
            label="Overlap Radius",
            kind="float",
            min=0.0,
            max=5.0,
            step=0.001,
        ),
        "add_colliders_btn": InspectField(
            path=None,
            label="Add Colliders",
            kind="button",
            action=lambda ref: ref.to_python().add_colliders(),
            is_serializable=False,
        ),
        "remove_colliders_btn": InspectField(
            path=None,
            label="Remove All Colliders",
            kind="button",
            action=lambda ref: ref.to_python().remove_all_colliders(),
            is_serializable=False,
        ),
    }

    def __init__(self, scale: float = 1.0, overlap_radius: float = 0.023):
        super().__init__(enabled=True)
        self.scale = scale
        self.overlap_radius = overlap_radius
        self._added_colliders: List[ColliderComponent] = []

    def _find_skeleton_controller(self):
        """Find SkeletonController on this entity or parent."""
        if self.entity is None:
            return None

        from termin.skeleton import SkeletonController

        # Check this entity
        comp = self.entity.get_component(SkeletonController)
        if comp is not None:
            return comp

        # Check parent
        parent_transform = self.entity.transform.parent
        if parent_transform is not None and parent_transform.entity is not None:
            parent_entity = parent_transform.entity
            comp = parent_entity.get_component(SkeletonController)
            if comp is not None:
                return comp

        return None

    def _get_all_bone_entities(self) -> List[Entity]:
        """Get all bone entities from skeleton."""
        from termin._native import log

        skeleton_controller = self._find_skeleton_controller()
        if skeleton_controller is None:
            log.warn("[HumanModelCollider] SkeletonController not found")
            return []

        return list(skeleton_controller.bone_entities)

    def _make_transform(self, cx: float, cy: float, cz: float) -> GeneralPose3:
        """Create transform for collider center offset."""
        s = self.scale
        return GeneralPose3(Quat.identity(), Vec3(cx * s, cy * s, cz * s))

    def _add_collider_to_bone(self, bone_entity: Entity, name: str) -> bool:
        """Add appropriate collider to bone based on name. Returns True if added."""
        s = self.scale
        overlap = self.overlap_radius * s

        collider = None

        if name.endswith("Spine"):
            collider = CapsuleCollider(
                0.03,  # half_height
                0.014 + overlap,
                self._make_transform(0, 0.003, 0.001)
            )

        elif "Head" in name and "HeadTop" not in name:
            collider = SphereCollider(
                0.011 * s + overlap,
                self._make_transform(0, 0.009, 0.003)
            )

        elif "LeftUpLeg" in name or "RightUpLeg" in name:
            collider = CapsuleCollider(
                0.025 * s,
                0.008 + overlap,
                self._make_transform(0, 0.02, 0)
            )

        elif "LeftLeg" in name or "RightLeg" in name:
            # Exclude UpLeg
            if "UpLeg" not in name:
                collider = CapsuleCollider(
                    0.025 * s,
                    0.008 + overlap,
                    self._make_transform(0, 0.02, 0)
                )

        elif "LeftForeArm" in name or "RightForeArm" in name:
            collider = CapsuleCollider(
                0.015 * s,
                0.006 + overlap,
                self._make_transform(0, 0.01, 0)
            )

        elif "LeftArm" in name or "RightArm" in name:
            # Exclude ForeArm
            if "ForeArm" not in name:
                collider = CapsuleCollider(
                    0.015 * s,
                    0.006 + overlap,
                    self._make_transform(0, 0.01, 0)
                )

        elif "LeftFoot" in name or "RightFoot" in name:
            collider = CapsuleCollider(
                0.015 * s,
                0.008 + overlap,
                self._make_transform(0, 0.007, 0)
            )

        elif name.endswith("LeftHand") or name.endswith("RightHand"):
            collider = CapsuleCollider(
                0.015 * s,
                0.008 + overlap,
                self._make_transform(0, 0.007, 0)
            )

        if collider is not None:
            comp = ColliderComponent(collider)
            bone_entity.add_component(comp)
            self._added_colliders.append(comp)
            return True

        return False

    def add_colliders(self):
        """Add colliders to all matching bone entities."""
        from termin._native import log

        self.remove_all_colliders()

        bone_entities = self._get_all_bone_entities()
        if not bone_entities:
            log.warn("[HumanModelCollider] No bone entities found")
            return

        added_count = 0
        for bone_entity in bone_entities:
            name = bone_entity.name or ""
            if self._add_collider_to_bone(bone_entity, name):
                added_count += 1
                log.info(f"[HumanModelCollider] Added collider to {name}")

        log.info(f"[HumanModelCollider] Added {added_count} colliders")

    def remove_all_colliders(self):
        """Remove all colliders added by this component."""
        from termin._native import log

        for comp in self._added_colliders:
            if comp.entity is not None:
                comp.entity.remove_component(comp)

        removed = len(self._added_colliders)
        self._added_colliders.clear()

        # Also scan bone entities for any remaining ColliderComponent
        bone_entities = self._get_all_bone_entities()
        for bone_entity in bone_entities:
            to_remove = [c for c in bone_entity.components if isinstance(c, ColliderComponent)]
            for comp in to_remove:
                bone_entity.remove_component(comp)
                removed += 1

        if removed > 0:
            log.info(f"[HumanModelCollider] Removed {removed} colliders")
