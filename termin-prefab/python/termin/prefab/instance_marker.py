"""PrefabInstanceMarker - component marking an Entity as a prefab instance."""

from __future__ import annotations

from typing import Any, Protocol, cast

import numpy as np

from termin.inspect import InspectField
from termin.scene.python_component import PythonComponent
from termin_assets import get_resource_manager


class PrefabResourceManager(Protocol):
    """Resource-manager surface needed by PrefabInstanceMarker."""

    def get_prefab_by_uuid(self, uuid: str) -> Any:
        ...


class PrefabInstanceMarker(PythonComponent):
    """
    Marker component linking an Entity to its source PrefabAsset.

    Stores the prefab UUID, property overrides, and structural changes.
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
            is_serializable=False,
        ),
        "override_count": InspectField(
            label="Overrides",
            kind="int",
            read_only=True,
            is_serializable=False,
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
        self._prefab_name: str = ""
        self.overrides: dict[str, Any] = overrides if overrides is not None else {}
        self.added_children: list[str] = added_children if added_children is not None else []
        self.removed_children: list[str] = removed_children if removed_children is not None else []

    def set_override(self, path: str, value: Any) -> None:
        """Record an override for a property path."""
        self.overrides[path] = self._serialize_value(value)

    def clear_override(self, path: str) -> None:
        """Remove an override, reverting to prefab value."""
        self.overrides.pop(path, None)

    def clear_all_overrides(self) -> None:
        """Remove all overrides, reverting everything to prefab values."""
        self.overrides.clear()

    def is_overridden(self, path: str) -> bool:
        """Check if a property path is overridden."""
        return path in self.overrides

    def get_override(self, path: str) -> Any | None:
        """Get the override value for a path."""
        return self.overrides.get(path)

    def get_overridden_paths(self) -> list[str]:
        """Get list of all overridden property paths."""
        return list(self.overrides.keys())

    def mark_child_added(self, child_uuid: str) -> None:
        """Mark a child as added, not from prefab."""
        if child_uuid not in self.added_children:
            self.added_children.append(child_uuid)

    def mark_child_removed(self, prefab_child_uuid: str) -> None:
        """Mark a prefab child as removed in this instance."""
        if prefab_child_uuid not in self.removed_children:
            self.removed_children.append(prefab_child_uuid)

    def is_child_added(self, child_uuid: str) -> bool:
        """Check if child was added, not from prefab."""
        return child_uuid in self.added_children

    def is_child_removed(self, prefab_child_uuid: str) -> bool:
        """Check if prefab child was removed in this instance."""
        return prefab_child_uuid in self.removed_children

    def get_prefab_asset(self) -> Any | None:
        """Get the source PrefabAsset."""
        if not self.prefab_uuid:
            return None

        resource_manager = get_resource_manager()
        if resource_manager is None:
            return None
        rm = cast(PrefabResourceManager, resource_manager)
        return rm.get_prefab_by_uuid(self.prefab_uuid)

    def refresh_from_prefab(self) -> bool:
        """Refresh non-overridden properties from prefab."""
        prefab = self.get_prefab_asset()
        if prefab is None:
            return False

        prefab.apply_to_instance(self.entity)
        return True

    def on_added(self) -> None:
        """Register in PrefabRegistry when added."""
        if self.prefab_uuid and self.entity:
            from termin.prefab.registry import PrefabRegistry

            PrefabRegistry.register(self.prefab_uuid, self.entity)

        self._update_prefab_name()

    def on_removed(self) -> None:
        """Unregister from PrefabRegistry when removed."""
        if self.prefab_uuid and self.entity:
            from termin.prefab.registry import PrefabRegistry

            PrefabRegistry.unregister(self.prefab_uuid, self.entity)

    def _update_prefab_name(self) -> None:
        """Update cached prefab name."""
        prefab = self.get_prefab_asset()
        if prefab:
            self._prefab_name = prefab.name
        else:
            self._prefab_name = f"<missing: {self.prefab_uuid[:8]}...>"

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

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """Serialize a value for storage in overrides."""
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, (list, tuple)):
            return [PrefabInstanceMarker._serialize_value(v) for v in value]
        if isinstance(value, dict):
            return {k: PrefabInstanceMarker._serialize_value(v) for k, v in value.items()}
        return {"__ref__": "uuid", "uuid": value.uuid}

    @staticmethod
    def _deserialize_value(value: Any, context=None) -> Any:
        """Deserialize a value from overrides storage."""
        if isinstance(value, dict):
            if value.get("__ref__") == "uuid":
                return value
            if value.get("__ref__") == "name":
                return value
            return {k: PrefabInstanceMarker._deserialize_value(v, context) for k, v in value.items()}
        if isinstance(value, list):
            if all(isinstance(x, (int, float)) for x in value):
                return np.array(value, dtype=np.float32)
            return [PrefabInstanceMarker._deserialize_value(v, context) for v in value]
        return value
