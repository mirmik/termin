"""EntityHandle - lazy reference to Entity by UUID."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from termin.visualization.core.entity import Entity
    from termin.visualization.core.scene import Scene


class EntityHandle:
    """
    Lazy reference to Entity by UUID.

    Used when Entity might not exist yet during deserialization.
    Resolves to actual Entity on first access via scene.

    Usage:
        handle = EntityHandle(uuid="...")
        handle.scene = scene  # Set scene for resolution
        entity = handle.entity  # Resolves and caches
    """

    __slots__ = ("_uuid", "_entity", "_scene")

    def __init__(self, uuid: str, entity: "Entity | None" = None):
        """
        Initialize EntityHandle.

        Args:
            uuid: UUID of the target entity
            entity: Pre-resolved entity (optional, for when entity is already known)
        """
        self._uuid = uuid
        self._entity: "Entity | None" = entity
        self._scene: "Scene | None" = None

    @property
    def uuid(self) -> str:
        """UUID of the target entity."""
        return self._uuid

    @property
    def scene(self) -> "Scene | None":
        """Scene used for resolution."""
        return self._scene

    @scene.setter
    def scene(self, value: "Scene | None") -> None:
        """Set scene for resolution."""
        self._scene = value

    @property
    def entity(self) -> "Entity | None":
        """
        Get the referenced Entity.

        Resolves lazily on first access if not already resolved.
        """
        if self._entity is not None:
            return self._entity

        if self._scene is None:
            return None

        self._entity = self._scene.find_entity_by_uuid(self._uuid)
        return self._entity

    @property
    def name(self) -> str:
        """Get entity name, or UUID if not resolved."""
        if self._entity is not None:
            return self._entity.name
        return f"<{self._uuid[:8]}...>"

    @property
    def is_resolved(self) -> bool:
        """Check if entity has been resolved."""
        return self._entity is not None

    def resolve(self, scene: "Scene") -> "Entity | None":
        """
        Explicitly resolve entity using given scene.

        Args:
            scene: Scene to search in

        Returns:
            Resolved Entity or None
        """
        self._scene = scene
        return self.entity

    @classmethod
    def from_entity(cls, entity: "Entity") -> "EntityHandle":
        """Create handle from existing Entity."""
        handle = cls(uuid=entity.uuid, entity=entity)
        handle._scene = entity.scene
        return handle

    def __repr__(self) -> str:
        status = "resolved" if self._entity else "unresolved"
        return f"<EntityHandle {self._uuid[:8]}... ({status})>"
