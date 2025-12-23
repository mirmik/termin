"""
PrefabAsset — Asset for .prefab files with hot-reload support.

A prefab is a reusable entity hierarchy that can be instantiated into scenes.
Instances maintain a link to the source prefab and can override properties.

NOTE: This class has some deviations from the standard DataAsset pattern:

1. from_file() reads content immediately instead of lazy loading.
   Standard pattern defers reading until .data is accessed.

2. UUID is stored inside the .prefab JSON file, not in a separate .meta file.
   This requires manual UUID extraction in _parse_content().

3. _on_loaded() auto-saves the file if UUID was missing.
   This ensures all prefabs get persistent UUIDs.

These deviations exist because prefabs are self-contained JSON documents
that embed their own metadata. Since prefabs are typically small files
(a few KB), eager loading does not significantly impact engine performance.

Potential fix path:
    1. Change from_file() to use lazy loading (data=None, source_path=path)
    2. Extract UUID in _parse_spec_fields() or accept spec-less design
    3. Document the "UUID in content" pattern as intentional
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

import numpy as np

from termin.assets.data_asset import DataAsset

if TYPE_CHECKING:
    from termin.visualization.core.entity import Entity
    from termin.kinematic.general_transform import GeneralTransform3


def _numpy_encoder(obj: Any) -> Any:
    """JSON encoder for numpy arrays."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.float32, np.float64)):
        return float(obj)
    if isinstance(obj, (np.int32, np.int64)):
        return int(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class PrefabAsset(DataAsset[dict]):
    """
    Asset for .prefab files.

    Stores serialized entity hierarchy data.
    Supports hot-reload with automatic update of all instances.

    File format:
    {
        "version": "2.0",
        "uuid": "prefab-uuid",
        "root": {
            "name": "...",
            "pose": {...},
            "components": [...],
            "children": [...]
        }
    }
    """

    VERSION = "2.0"
    _uses_binary = False  # JSON format

    def __init__(
        self,
        data: dict | None = None,
        name: str = "prefab",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=data, name=name, source_path=source_path, uuid=uuid)

    # --- Properties ---

    @property
    def root_data(self) -> dict | None:
        """Get serialized root entity data."""
        if self._data is None:
            return None
        return self._data.get("root")

    @property
    def version(self) -> str:
        """Get prefab format version."""
        if self._data is None:
            return self.VERSION
        return self._data.get("version", "1.0")

    # --- Instantiation ---

    def instantiate(
        self,
        parent: "GeneralTransform3 | None" = None,
        position: tuple[float, float, float] | None = None,
        name: str | None = None,
    ) -> "Entity":
        """
        Create an instance of this prefab.

        Creates a new Entity hierarchy from prefab data, with:
        - New UUIDs for all entities
        - PrefabInstanceMarker on the root entity
        - Registration in PrefabRegistry

        Args:
            parent: Parent transform to attach to
            position: Override position (local)
            name: Override name for root entity

        Returns:
            Root Entity of the instance
        """
        from termin.visualization.core.entity import Entity
        from termin.visualization.core.prefab_instance_marker import PrefabInstanceMarker
        from termin.visualization.core.prefab_registry import PrefabRegistry

        # Ensure prefab is loaded
        self.ensure_loaded()

        root_data = self.root_data
        if root_data is None:
            raise ValueError(f"Prefab '{self.name}' has no root data")

        # Deserialize with new UUIDs
        entity = Entity.deserialize(root_data, context=None)

        # Override name if provided
        if name is not None:
            entity.name = name

        # Override position if provided
        if position is not None:
            pose = entity.transform.local_pose()
            pose.lin[...] = position
            entity.transform.relocate(pose)

        # Add PrefabInstanceMarker (if not already present from nested prefab)
        existing_marker = entity.get_component(PrefabInstanceMarker)
        if existing_marker is None:
            marker = PrefabInstanceMarker(prefab_uuid=self.uuid)
            entity.add_component(marker)

        # Attach to parent
        if parent is not None:
            parent.add_child(entity.transform)

        return entity

    # --- Hot-Reload ---

    def update_from(self, other: "PrefabAsset") -> None:
        """
        Hot-reload: update data and refresh all instances.

        Called when the .prefab file is modified.

        Args:
            other: Newly loaded PrefabAsset with updated data
        """
        self._data = other._data
        self._bump_version()
        self._update_all_instances()

    def _update_all_instances(self) -> None:
        """Update all instances of this prefab."""
        from termin.visualization.core.prefab_registry import PrefabRegistry

        instances = PrefabRegistry.get_instances(self.uuid)
        for entity in instances:
            self.apply_to_instance(entity)

    def apply_to_instance(self, entity: "Entity") -> None:
        """
        Apply prefab data to an instance, preserving overrides.

        Iterates over all prefab properties and applies those
        that are not overridden in the instance.

        Args:
            entity: Instance entity with PrefabInstanceMarker
        """
        from termin.visualization.core.prefab_instance_marker import PrefabInstanceMarker
        from termin.visualization.core.property_path import PropertyPath

        marker = entity.get_component(PrefabInstanceMarker)
        if marker is None:
            return

        root_data = self.root_data
        if root_data is None:
            return

        # Iterate over all prefab properties
        for path, value in PropertyPath.iter_from_data(root_data):
            # Skip if overridden
            if marker.is_overridden(path):
                continue

            # Skip structural properties that might conflict
            if path == "name" and entity.name != root_data.get("name"):
                # Name was changed, treat as implicit override
                continue

            # Apply value from prefab
            try:
                # Deserialize value if needed
                deserialized = self._deserialize_property_value(path, value)
                PropertyPath.set(entity, path, deserialized)
            except (KeyError, AttributeError) as e:
                # Path doesn't exist in instance (structural difference)
                print(f"[PrefabAsset] Cannot apply {path}: {e}")

    def _deserialize_property_value(self, path: str, value: Any) -> Any:
        """
        Deserialize a property value for application.

        Handles resource references, vectors, etc.
        """
        # Handle resource references
        if isinstance(value, dict):
            if "uuid" in value:
                return self._resolve_resource_by_uuid(value["uuid"], path)
            return value

        # Handle vectors (lists of numbers)
        if isinstance(value, list) and value and all(isinstance(x, (int, float)) for x in value):
            return np.array(value, dtype=np.float32)

        return value

    def _resolve_resource_by_uuid(self, uuid: str, path: str) -> Any:
        """Resolve a resource reference by UUID."""
        from termin.assets.resources import ResourceManager

        rm = ResourceManager.instance()

        # Determine resource type from path
        if "material" in path.lower():
            return rm.get_material_by_uuid(uuid)
        if "mesh" in path.lower():
            return rm.get_mesh_by_uuid(uuid)
        if "skeleton" in path.lower():
            return rm.get_skeleton_by_uuid(uuid)

        # Generic lookup
        return rm.get_asset_by_uuid(uuid)

    # --- Content Parsing ---

    def _parse_content(self, content: str) -> dict | None:
        """Parse JSON content into prefab data."""
        data = json.loads(content)

        # Extract UUID from file if present
        file_uuid = data.get("uuid")
        if file_uuid:
            self._uuid = file_uuid
            self._runtime_id = hash(self._uuid) & 0xFFFFFFFFFFFFFFFF

        return data

    def _on_loaded(self) -> None:
        """After loading, save file if it didn't have UUID."""
        if self._source_path is not None and self._data is not None:
            try:
                if "uuid" not in self._data:
                    self._data["uuid"] = self.uuid
                    self.save_to_file()
            except Exception:
                pass

    # --- Saving ---

    def save_spec_file(self) -> bool:
        """Prefabs store UUID in the file itself, not in spec."""
        return self.save_to_file()

    def save_to_file(self, path: str | Path | None = None) -> bool:
        """
        Save prefab to .prefab file.

        Args:
            path: Path to save to. If None, uses source_path.

        Returns:
            True if saved successfully.
        """
        if self._data is None:
            return False

        save_path = Path(path) if path else self._source_path
        if save_path is None:
            return False

        try:
            # Ensure UUID and version are in data
            self._data["uuid"] = self.uuid
            self._data["version"] = self.VERSION

            json_str = json.dumps(
                self._data,
                indent=2,
                ensure_ascii=False,
                default=_numpy_encoder,
            )

            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(json_str)

            self._source_path = Path(save_path)
            self.mark_just_saved()
            return True
        except Exception as e:
            print(f"[PrefabAsset] Failed to save: {e}")
            return False

    # --- Factory Methods ---

    @classmethod
    def from_file(cls, path: str | Path, name: str | None = None) -> "PrefabAsset":
        """
        Create PrefabAsset from .prefab file.

        Args:
            path: Path to .prefab file
            name: Name override (defaults to filename stem)

        Returns:
            PrefabAsset instance
        """
        path = Path(path)

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        file_uuid = data.get("uuid")

        return cls(
            data=data,
            name=name or path.stem,
            source_path=path,
            uuid=file_uuid,
        )

    @classmethod
    def from_entity(
        cls,
        entity: "Entity",
        name: str | None = None,
        source_path: str | Path | None = None,
    ) -> "PrefabAsset":
        """
        Create PrefabAsset from an existing Entity.

        Args:
            entity: Entity to create prefab from
            name: Prefab name (defaults to entity name)
            source_path: Path to save to

        Returns:
            PrefabAsset instance
        """
        entity_data = entity.serialize()
        if entity_data is None:
            raise ValueError(f"Entity '{entity.name}' is not serializable")

        data = {
            "version": cls.VERSION,
            "root": entity_data,
        }

        return cls(
            data=data,
            name=name or entity.name,
            source_path=source_path,
        )

    # --- Utilities ---

    def get_entity_count(self) -> int:
        """Count total entities in prefab hierarchy."""
        return self._count_entities(self.root_data) if self.root_data else 0

    def _count_entities(self, data: dict) -> int:
        """Recursively count entities."""
        count = 1
        for child in data.get("children", []):
            count += self._count_entities(child)
        return count

    def get_component_types(self) -> list[str]:
        """Get list of component types used in prefab."""
        types = set()
        self._collect_component_types(self.root_data, types)
        return sorted(types)

    def _collect_component_types(self, data: dict | None, types: set[str]) -> None:
        """Recursively collect component types."""
        if data is None:
            return
        for comp in data.get("components", []):
            comp_type = comp.get("type")
            if comp_type:
                types.add(comp_type)
        for child in data.get("children", []):
            self._collect_component_types(child, types)
