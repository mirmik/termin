"""EntityHandle - lazy reference to Entity by UUID."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from termin.visualization.core.entity import Entity


class EntityHandle:
    """
    Lazy reference to Entity by UUID.

    Used when Entity might not exist yet during deserialization.
    Resolves to actual Entity on first access via global EntityRegistry.

    Usage:
        handle = EntityHandle(uuid="...")
        entity = handle.entity  # Resolves and caches
    """

    __slots__ = ("_uuid", "_entity")

    def __init__(self, uuid: str, entity: "Entity | None" = None):
        """
        Initialize EntityHandle.

        Args:
            uuid: UUID of the target entity
            entity: Pre-resolved entity (optional, for when entity is already known)
        """
        self._uuid = uuid
        self._entity: "Entity | None" = entity

    @property
    def uuid(self) -> str:
        """UUID of the target entity."""
        return self._uuid

    @property
    def entity(self) -> "Entity | None":
        """
        Get the referenced Entity.

        Resolves lazily on first access if not already resolved.
        """
        if self._entity is not None:
            return self._entity

        from termin.visualization.core.entity_registry import EntityRegistry
        self._entity = EntityRegistry.instance().get(self._uuid)
        return self._entity

    @property
    def name(self) -> str:
        """Get entity name, or UUID if not resolved."""
        entity = self.entity
        if entity is not None:
            return entity.name
        return f"<{self._uuid[:8]}...>"

    @property
    def is_resolved(self) -> bool:
        """Check if entity has been resolved."""
        return self._entity is not None

    @classmethod
    def from_entity(cls, entity: "Entity") -> "EntityHandle":
        """Create handle from existing Entity."""
        return cls(uuid=entity.uuid, entity=entity)

    def __repr__(self) -> str:
        status = "resolved" if self._entity else "unresolved"
        return f"<EntityHandle {self._uuid[:8]}... ({status})>"
