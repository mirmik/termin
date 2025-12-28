"""
PrefabInstanceMarker — component marking an Entity as a prefab instance.

Stores the link to the source prefab and tracks property overrides.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, TYPE_CHECKING

import numpy as np

from termin.visualization.core.python_component import PythonComponent
from termin.editor.inspect_field import InspectField

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene


class PrefabInstanceMarker(PythonComponent):
    """
    Marker component linking an Entity to its source PrefabAsset.

    Stores:
    - Reference to prefab (uuid)
    - Overridden properties (path -> value)
    - Structural changes (added/removed children)

    When the prefab is hot-reloaded, non-overridden properties are updated
    from the new prefab data, while overridden properties are preserved.
    """

    inspect_fields = {
        "prefab_uuid": InspectField(
            path="prefab_uuid",
            label="Prefab UUID",
            kind="string",
            read_only=True,
        ),
        "prefab_name": InspectField(
            path="_prefab_name",
            label="Prefab",
            kind="string",
            read_only=True,
            non_serializable=True,
        ),
        "override_count": InspectField(
            label="Overrides",
            kind="int",
            read_only=True,
            non_serializable=True,
            getter=lambda self: len(self.overrides),
        ),
    }

    def __init__(
        self,
        prefab_uuid: str = "",
        overrides: dict[str, Any] | None = None,
        added_children: list[str] | None = None,
        removed_children: list[str] | None = None,
    ):
        super().__init__()
        self.prefab_uuid: str = prefab_uuid
        self._prefab_name: str = ""  # Cached name for display

        # path -> serialized value
        self.overrides: dict[str, Any] = overrides if overrides is not None else {}

        # UUIDs of children added to this instance (not in prefab)
        self.added_children: list[str] = added_children if added_children is not None else []

        # UUIDs of children from prefab that were removed in this instance
        self.removed_children: list[str] = removed_children if removed_children is not None else []

    # --- Override Management ---

    def set_override(self, path: str, value: Any) -> None:
        """
        Record an override for a property path.

        Args:
            path: Property path (e.g., "transform.position", "components/MeshRenderer/material")
            value: New value (will be serialized for storage)
        """
        self.overrides[path] = self._serialize_value(value)

    def clear_override(self, path: str) -> None:
        """
        Remove an override, reverting to prefab value.

        Args:
            path: Property path to clear
        """
        self.overrides.pop(path, None)

    def clear_all_overrides(self) -> None:
        """Remove all overrides, reverting everything to prefab values."""
        self.overrides.clear()

    def is_overridden(self, path: str) -> bool:
        """
        Check if a property path is overridden.

        Args:
            path: Property path

        Returns:
            True if the path has an override
        """
        return path in self.overrides

    def get_override(self, path: str) -> Any | None:
        """
        Get the override value for a path.

        Args:
            path: Property path

        Returns:
            Override value or None if not overridden
        """
        return self.overrides.get(path)

    def get_overridden_paths(self) -> list[str]:
        """
        Get list of all overridden property paths.

        Returns:
            List of paths
        """
        return list(self.overrides.keys())

    # --- Structural Changes ---

    def mark_child_added(self, child_uuid: str) -> None:
        """
        Mark a child as added (not from prefab).

        Args:
            child_uuid: UUID of the added child entity
        """
        if child_uuid not in self.added_children:
            self.added_children.append(child_uuid)

    def mark_child_removed(self, prefab_child_uuid: str) -> None:
        """
        Mark a prefab child as removed in this instance.

        Args:
            prefab_child_uuid: UUID of the child in the prefab
        """
        if prefab_child_uuid not in self.removed_children:
            self.removed_children.append(prefab_child_uuid)

    def is_child_added(self, child_uuid: str) -> bool:
        """Check if child was added (not from prefab)."""
        return child_uuid in self.added_children

    def is_child_removed(self, prefab_child_uuid: str) -> bool:
        """Check if prefab child was removed in this instance."""
        return prefab_child_uuid in self.removed_children

    # --- Prefab Access ---

    def get_prefab_asset(self) -> Any | None:
        """
        Get the source PrefabAsset.

        Returns:
            PrefabAsset or None if not found
        """
        if not self.prefab_uuid:
            return None

        from termin.visualization.core.resources import ResourceManager
        rm = ResourceManager.instance()
        return rm.get_prefab_by_uuid(self.prefab_uuid)

    def refresh_from_prefab(self) -> bool:
        """
        Refresh non-overridden properties from prefab.

        Called during hot-reload.

        Returns:
            True if refresh was successful
        """
        prefab = self.get_prefab_asset()
        if prefab is None:
            return False

        prefab.apply_to_instance(self.entity)
        return True

    # --- Lifecycle ---

    def on_added(self, scene: "Scene") -> None:
        """Register in PrefabRegistry when added to scene."""
        if self.prefab_uuid and self.entity:
            from termin.visualization.core.prefab_registry import PrefabRegistry
            PrefabRegistry.register(self.prefab_uuid, self.entity)

        # Cache prefab name for display
        self._update_prefab_name()

    def on_removed(self) -> None:
        """Unregister from PrefabRegistry when removed."""
        if self.prefab_uuid and self.entity:
            from termin.visualization.core.prefab_registry import PrefabRegistry
            PrefabRegistry.unregister(self.prefab_uuid, self.entity)

    def _update_prefab_name(self) -> None:
        """Update cached prefab name."""
        prefab = self.get_prefab_asset()
        if prefab:
            self._prefab_name = prefab.name
        else:
            self._prefab_name = f"<missing: {self.prefab_uuid[:8]}...>"

    # --- Serialization ---

    def serialize_data(self) -> dict:
        """Serialize marker data."""
        data = {
            "prefab_uuid": self.prefab_uuid,
        }

        if self.overrides:
            data["overrides"] = self.overrides

        if self.added_children:
            data["added_children"] = self.added_children

        if self.removed_children:
            data["removed_children"] = self.removed_children

        return data

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "PrefabInstanceMarker":
        """Deserialize marker from data."""
        return cls(
            prefab_uuid=data.get("prefab_uuid", ""),
            overrides=data.get("overrides"),
            added_children=data.get("added_children"),
            removed_children=data.get("removed_children"),
        )

    # --- Value Serialization Helpers ---

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """
        Serialize a value for storage in overrides.

        Converts numpy arrays to lists, etc.
        """
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, (list, tuple)):
            return [PrefabInstanceMarker._serialize_value(v) for v in value]
        if isinstance(value, dict):
            return {k: PrefabInstanceMarker._serialize_value(v) for k, v in value.items()}
        # For complex objects (Material, Mesh, etc.) store reference
        if hasattr(value, "uuid"):
            return {"__ref__": "uuid", "uuid": value.uuid}
        if hasattr(value, "name") and hasattr(value, "__class__"):
            return {"__ref__": "name", "type": value.__class__.__name__, "name": value.name}
        return value

    @staticmethod
    def _deserialize_value(value: Any, context=None) -> Any:
        """
        Deserialize a value from overrides storage.
        """
        if isinstance(value, dict):
            if value.get("__ref__") == "uuid":
                # TODO: resolve by UUID
                return value
            if value.get("__ref__") == "name":
                # TODO: resolve by name
                return value
            return {k: PrefabInstanceMarker._deserialize_value(v, context) for k, v in value.items()}
        if isinstance(value, list):
            # Check if it looks like a vector
            if all(isinstance(x, (int, float)) for x in value):
                return np.array(value, dtype=np.float32)
            return [PrefabInstanceMarker._deserialize_value(v, context) for v in value]
        return value
