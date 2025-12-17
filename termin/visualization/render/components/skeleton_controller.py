"""SkeletonController - Component that manages skeleton for skinned meshes."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from termin.editor.inspect_field import InspectField
from termin.visualization.core.entity import Component

if TYPE_CHECKING:
    from termin.skeleton.skeleton import SkeletonData, SkeletonInstance
    from termin.skeleton.skeleton_asset import SkeletonAsset
    from termin.visualization.core.entity import Entity


class SkeletonController(Component):
    """
    Component that manages skeleton data and bone entity references.

    References SkeletonAsset and creates SkeletonInstance on demand.
    SkinnedMeshRenderer components reference this to get bone matrices.

    Serialization uses standard InspectFields:
        - skeleton: SkeletonAsset reference (stored as UUID)
        - bone_entities: List of Entity UUIDs
    """

    inspect_fields = {
        **Component.inspect_fields,
        "skeleton": InspectField(
            label="Skeleton",
            kind="skeleton",
            getter=lambda self: self._skeleton_data,
            setter=lambda self, v: self._set_skeleton_data(v),
        ),
        "bone_entities": InspectField(
            label="Bone Entities",
            kind="entity_list",
            read_only=True,
            getter=lambda self: self._bone_entity_uuids or [],
            setter=lambda self, v: self._set_bone_entity_uuids(v),
        ),
    }

    def __init__(
        self,
        skeleton_data: "SkeletonData | None" = None,
        bone_entities: "List[Entity] | None" = None,
    ):
        """
        Initialize SkeletonController.

        Args:
            skeleton_data: The skeleton template with bone hierarchy and IBM
            bone_entities: List of Entity objects for each bone (same order as skeleton_data.bones)
        """
        super().__init__(enabled=True)
        self._skeleton_data: "SkeletonData | None" = skeleton_data
        self._bone_entities: "List[Entity] | None" = bone_entities
        self._skeleton_instance: "SkeletonInstance | None" = None

        # For serialization - store bone entity UUIDs
        self._bone_entity_uuids: List[str] | None = None
        if bone_entities is not None:
            self._bone_entity_uuids = [e.uuid for e in bone_entities]

    def _set_skeleton_data(self, value: "SkeletonData | None") -> None:
        """Setter for skeleton_data InspectField."""
        self._skeleton_data = value
        self._skeleton_instance = None  # Invalidate cached instance

    def _set_bone_entity_uuids(self, value: List[str] | None) -> None:
        """Setter for bone_entities InspectField."""
        self._bone_entity_uuids = value
        self._bone_entities = None  # Need to re-resolve
        self._skeleton_instance = None  # Invalidate cached instance

    @property
    def skeleton_data(self) -> "SkeletonData | None":
        """Get the skeleton template."""
        return self._skeleton_data

    @property
    def skeleton_instance(self) -> "SkeletonInstance | None":
        """
        Get or create the SkeletonInstance.

        Creates instance lazily on first access.
        """
        if self._skeleton_instance is None and self._skeleton_data is not None:
            if self._bone_entities is not None:
                from termin.skeleton.skeleton import SkeletonInstance
                self._skeleton_instance = SkeletonInstance(
                    self._skeleton_data,
                    bone_entities=self._bone_entities,
                )
            else:
                # Try to resolve bone entities from UUIDs
                self._resolve_bone_entities()
                if self._bone_entities is not None:
                    from termin.skeleton.skeleton import SkeletonInstance
                    self._skeleton_instance = SkeletonInstance(
                        self._skeleton_data,
                        bone_entities=self._bone_entities,
                    )
        return self._skeleton_instance

    def _resolve_bone_entities(self) -> None:
        """Resolve bone entities from stored UUIDs via scene."""
        if self._bone_entity_uuids is None or self.entity is None:
            return

        scene = self.entity.scene
        if scene is None:
            return

        # Resolve each UUID to Entity
        bone_entities: "List[Entity]" = []
        for uuid in self._bone_entity_uuids:
            entity = scene.find_entity_by_uuid(uuid)
            if entity is not None:
                bone_entities.append(entity)
            else:
                print(f"[SkeletonController] WARNING: Could not find bone entity with UUID {uuid}")
                return  # Abort if any bone not found

        self._bone_entities = bone_entities

    def set_bone_entities(self, bone_entities: "List[Entity]") -> None:
        """Set bone entities and invalidate cached instance."""
        self._bone_entities = bone_entities
        self._bone_entity_uuids = [e.uuid for e in bone_entities]
        self._skeleton_instance = None
