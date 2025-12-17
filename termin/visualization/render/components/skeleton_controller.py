"""SkeletonController - Component that manages skeleton for skinned meshes."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from termin.visualization.core.entity import Component
from termin.skeleton.skeleton import SkeletonData, SkeletonInstance

if TYPE_CHECKING:
    from termin.visualization.core.entity import Entity


class SkeletonController(Component):
    """
    Component that manages skeleton data and bone entity references.

    Holds SkeletonData and creates SkeletonInstance on demand.
    SkinnedMeshRenderer components reference this to get bone matrices.

    Serialization:
        - SkeletonData is serialized inline
        - Bone entities are stored as names and resolved on load
    """

    def __init__(
        self,
        skeleton_data: SkeletonData | None = None,
        bone_entities: List["Entity"] | None = None,
    ):
        """
        Initialize SkeletonController.

        Args:
            skeleton_data: The skeleton template with bone hierarchy and IBM
            bone_entities: List of Entity objects for each bone (same order as skeleton_data.bones)
        """
        super().__init__(enabled=True)
        self._skeleton_data = skeleton_data
        self._bone_entities: List["Entity"] | None = bone_entities
        self._skeleton_instance: SkeletonInstance | None = None

        # For serialization - store bone entity names
        self._bone_entity_names: List[str] | None = None
        if bone_entities is not None:
            self._bone_entity_names = [e.name for e in bone_entities]

    @property
    def skeleton_data(self) -> SkeletonData | None:
        """Get the skeleton template."""
        return self._skeleton_data

    @property
    def skeleton_instance(self) -> SkeletonInstance | None:
        """
        Get or create the SkeletonInstance.

        Creates instance lazily on first access.
        """
        if self._skeleton_instance is None and self._skeleton_data is not None:
            if self._bone_entities is not None:
                self._skeleton_instance = SkeletonInstance(
                    self._skeleton_data,
                    bone_entities=self._bone_entities,
                )
            else:
                # Try to resolve bone entities from names
                self._resolve_bone_entities()
                if self._bone_entities is not None:
                    self._skeleton_instance = SkeletonInstance(
                        self._skeleton_data,
                        bone_entities=self._bone_entities,
                    )
        return self._skeleton_instance

    def _resolve_bone_entities(self) -> None:
        """Resolve bone entities from stored names by searching entity hierarchy."""
        if self._bone_entity_names is None or self.entity is None:
            return

        # Find root of hierarchy
        root = self.entity
        while root.transform.parent is not None:
            parent_entity = root.transform.parent.entity
            if parent_entity is not None:
                root = parent_entity
            else:
                break

        # Build name -> entity map from hierarchy
        entity_map: dict[str, "Entity"] = {}
        self._collect_entities(root, entity_map)

        # Resolve bone entities
        bone_entities: List["Entity"] = []
        for name in self._bone_entity_names:
            entity = entity_map.get(name)
            if entity is not None:
                bone_entities.append(entity)
            else:
                print(f"[SkeletonController] WARNING: Could not find bone entity {name!r}")
                return  # Abort if any bone not found

        self._bone_entities = bone_entities

    def _collect_entities(self, entity: "Entity", entity_map: dict[str, "Entity"]) -> None:
        """Recursively collect all entities into name map."""
        entity_map[entity.name] = entity
        for child_transform in entity.transform.children:
            if child_transform.entity is not None:
                self._collect_entities(child_transform.entity, entity_map)

    def set_bone_entities(self, bone_entities: List["Entity"]) -> None:
        """Set bone entities and invalidate cached instance."""
        self._bone_entities = bone_entities
        self._bone_entity_names = [e.name for e in bone_entities]
        self._skeleton_instance = None

    # --- Serialization ---

    def serialize_data(self) -> dict:
        """Serialize SkeletonController."""
        data: dict = {"enabled": self.enabled}

        if self._skeleton_data is not None:
            data["skeleton_data"] = self._skeleton_data.serialize()

        if self._bone_entity_names is not None:
            data["bone_entity_names"] = self._bone_entity_names

        return data

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "SkeletonController":
        """Deserialize SkeletonController."""
        skeleton_data = None
        if "skeleton_data" in data:
            skeleton_data = SkeletonData.deserialize(data["skeleton_data"])

        controller = cls(skeleton_data=skeleton_data, bone_entities=None)
        controller._bone_entity_names = data.get("bone_entity_names")
        controller.enabled = data.get("enabled", True)

        return controller
