"""SkeletonController - Component that manages skeleton for skinned meshes."""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from termin.editor.inspect_field import InspectField
from termin.visualization.core.entity import Component
from termin.visualization.core.entity_handle import EntityHandle

if TYPE_CHECKING:
    from termin.skeleton.skeleton import SkeletonData, SkeletonInstance
    from termin.visualization.core.entity import Entity


class SkeletonController(Component):
    """
    Component that manages skeleton data and bone entity references.

    References SkeletonData and creates SkeletonInstance on demand.
    SkinnedMeshRenderer components reference this to get bone matrices.

    Serialization uses standard InspectFields:
        - skeleton: SkeletonData reference (stored as UUID)
        - bone_entities: List[EntityHandle] (stored as list of UUIDs)
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
            getter=lambda self: self._bone_handles,
            setter=lambda self, v: self._set_bone_handles(v),
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
        self._skeleton_instance: "SkeletonInstance | None" = None
        self._pending_skeleton_uuid: str | None = None  # For lazy resolution after deserialization

        # Store bone references as EntityHandles
        self._bone_handles: List[EntityHandle] = []
        if bone_entities is not None:
            self._bone_handles = [EntityHandle.from_entity(e) for e in bone_entities]

    def _set_skeleton_data(self, value: "SkeletonData | None") -> None:
        """Setter for skeleton_data InspectField."""
        self._skeleton_data = value
        self._skeleton_instance = None  # Invalidate cached instance

    def _set_bone_handles(self, value: List[EntityHandle] | None) -> None:
        """Setter for bone_entities InspectField."""
        self._bone_handles = value if value else []
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
        Resolves EntityHandles to actual Entities via scene.
        """
        if self._skeleton_instance is None and self._skeleton_data is not None:
            bone_entities = self._resolve_bone_entities()
            if bone_entities is not None:
                from termin.skeleton.skeleton import SkeletonInstance
                self._skeleton_instance = SkeletonInstance(
                    self._skeleton_data,
                    bone_entities=bone_entities,
                )
        return self._skeleton_instance

    def _resolve_bone_entities(self) -> "List[Entity] | None":
        """Resolve EntityHandles to actual Entities via EntityRegistry."""
        if not self._bone_handles:
            return None

        bone_entities: "List[Entity]" = []

        for handle in self._bone_handles:
            # EntityHandle resolves via global EntityRegistry
            entity = handle.entity
            if entity is not None:
                bone_entities.append(entity)
            else:
                print(f"[SkeletonController] WARNING: Could not resolve bone entity {handle.uuid}")
                return None

        return bone_entities

    def set_bone_entities(self, bone_entities: "List[Entity]") -> None:
        """Set bone entities and invalidate cached instance."""
        self._bone_handles = [EntityHandle.from_entity(e) for e in bone_entities]
        self._skeleton_instance = None
