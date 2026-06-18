"""PrefabRegistry - global registry of prefab instances."""

from __future__ import annotations

import weakref
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin.scene import Entity


class PrefabRegistry:
    """
    Global registry of prefab instances.

    Tracks all live instances of each prefab using weak references.
    When a prefab is modified, we can quickly find and update all instances.
    """

    _instances: dict[str, weakref.WeakSet["Entity"]] = {}

    @classmethod
    def register(cls, prefab_uuid: str, entity: "Entity") -> None:
        """Register a prefab instance."""
        if not prefab_uuid:
            return

        if prefab_uuid not in cls._instances:
            cls._instances[prefab_uuid] = weakref.WeakSet()

        cls._instances[prefab_uuid].add(entity)

    @classmethod
    def unregister(cls, prefab_uuid: str, entity: "Entity") -> None:
        """Unregister a prefab instance."""
        if not prefab_uuid:
            return

        if prefab_uuid in cls._instances:
            cls._instances[prefab_uuid].discard(entity)

    @classmethod
    def get_instances(cls, prefab_uuid: str) -> list["Entity"]:
        """Get all live instances of a prefab."""
        if prefab_uuid not in cls._instances:
            return []
        return list(cls._instances[prefab_uuid])

    @classmethod
    def instance_count(cls, prefab_uuid: str) -> int:
        """Get count of live instances."""
        if prefab_uuid not in cls._instances:
            return 0
        return len(cls._instances[prefab_uuid])

    @classmethod
    def clear(cls) -> None:
        """Clear all registrations."""
        cls._instances.clear()

    @classmethod
    def clear_prefab(cls, prefab_uuid: str) -> None:
        """Clear registrations for a specific prefab."""
        cls._instances.pop(prefab_uuid, None)

    @classmethod
    def get_all_prefab_uuids(cls) -> list[str]:
        """Get list of all prefab UUIDs that have instances."""
        return list(cls._instances.keys())

    @classmethod
    def debug_dump(cls) -> dict[str, int]:
        """Get debug info about registry contents."""
        return {
            uuid: len(instances)
            for uuid, instances in cls._instances.items()
            if len(instances) > 0
        }
