"""
EntityRegistry - global registry for entity lookup by UUID.

Singleton pattern similar to ResourceManager.
Entities register themselves on creation and unregister on removal.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from weakref import WeakValueDictionary

if TYPE_CHECKING:
    from termin.visualization.core.entity import Entity


class EntityRegistry:
    """
    Global registry for entity lookup by UUID.

    Uses WeakValueDictionary to avoid preventing garbage collection.
    """

    _instance: Optional["EntityRegistry"] = None

    def __init__(self):
        self._entities: WeakValueDictionary[str, "Entity"] = WeakValueDictionary()

    @classmethod
    def instance(cls) -> "EntityRegistry":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    def register(self, entity: "Entity") -> None:
        """Register entity by UUID."""
        if entity.uuid:
            self._entities[entity.uuid] = entity

    def unregister(self, entity: "Entity") -> None:
        """Unregister entity."""
        if entity.uuid and entity.uuid in self._entities:
            del self._entities[entity.uuid]

    def get(self, uuid: str) -> Optional["Entity"]:
        """Get entity by UUID."""
        return self._entities.get(uuid)

    def clear(self) -> None:
        """Clear all registered entities."""
        self._entities.clear()


__all__ = ["EntityRegistry"]
