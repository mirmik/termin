"""
EntityRegistry - global registry for entity lookup by UUID and pick_id.

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
    Global registry for entity lookup by UUID and pick_id.

    Uses WeakValueDictionary for UUID lookup to avoid preventing garbage collection.
    Uses regular dict for pick_id lookup (pick_id is lazily assigned).
    """

    _instance: Optional["EntityRegistry"] = None

    def __init__(self):
        self._entities_by_uuid: WeakValueDictionary[str, "Entity"] = WeakValueDictionary()
        self._entities_by_pick_id: dict[int, "Entity"] = {}

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
            self._entities_by_uuid[entity.uuid] = entity

    def register_pick_id(self, pick_id: int, entity: "Entity") -> None:
        """Register entity by pick_id."""
        self._entities_by_pick_id[pick_id] = entity

    def unregister(self, entity: "Entity") -> None:
        """Unregister entity from UUID registry."""
        if entity.uuid and entity.uuid in self._entities_by_uuid:
            del self._entities_by_uuid[entity.uuid]

    def unregister_pick_id(self, pick_id: int) -> None:
        """Unregister entity from pick_id registry."""
        self._entities_by_pick_id.pop(pick_id, None)

    def get(self, uuid: str) -> Optional["Entity"]:
        """Get entity by UUID."""
        return self._entities_by_uuid.get(uuid)

    def get_by_pick_id(self, pick_id: int) -> Optional["Entity"]:
        """Get entity by pick_id."""
        return self._entities_by_pick_id.get(pick_id)

    def clear(self) -> None:
        """Clear all registered entities."""
        self._entities_by_uuid.clear()
        self._entities_by_pick_id.clear()

    def swap_registries(
        self,
        new_by_uuid: WeakValueDictionary[str, "Entity"],
        new_by_pick_id: dict[int, "Entity"],
    ) -> tuple[WeakValueDictionary[str, "Entity"], dict[int, "Entity"]]:
        """
        Swap registries and return old ones.
        Used for game mode isolation.
        """
        old_by_uuid = self._entities_by_uuid
        old_by_pick_id = self._entities_by_pick_id
        self._entities_by_uuid = new_by_uuid
        self._entities_by_pick_id = new_by_pick_id
        return old_by_uuid, old_by_pick_id


__all__ = ["EntityRegistry"]
