"""PrefabAsset - asset for reusable entity hierarchies."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

import numpy as np

from tcbase import log
from termin_assets import DataAsset

if TYPE_CHECKING:
    from termin.kinematic.general_transform import GeneralTransform3
    from termin.visualization.core.entity import Entity


def _numpy_encoder(obj: Any) -> Any:
    """JSON encoder for numpy values."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.float32, np.float64)):
        return float(obj)
    if isinstance(obj, (np.int32, np.int64)):
        return int(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class PrefabAsset(DataAsset[dict]):
    """Asset for .prefab files."""

    VERSION = "2.0"
    _uses_binary = False

    def __init__(
        self,
        data: dict | None = None,
        name: str = "prefab",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=data, name=name, source_path=source_path, uuid=uuid)

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

    def instantiate(
        self,
        parent: "GeneralTransform3 | None" = None,
        position: tuple[float, float, float] | None = None,
        name: str | None = None,
    ) -> "Entity":
        """Create an instance of this prefab."""
        from termin.visualization.core.entity import Entity
        from termin.visualization.core.prefab_instance_marker import PrefabInstanceMarker

        self.ensure_loaded()

        root_data = self.root_data
        if root_data is None:
            raise ValueError(f"Prefab '{self.name}' has no root data")

        entity = Entity.deserialize(root_data, context=None)

        if name is not None:
            entity.name = name

        if position is not None:
            pose = entity.transform.local_pose()
            pose.lin[...] = position
            entity.transform.relocate(pose)

        existing_marker = entity.get_component(PrefabInstanceMarker)
        if existing_marker is None:
            marker = PrefabInstanceMarker(prefab_uuid=self.uuid)
            entity.add_component(marker)

        if parent is not None:
            parent.add_child(entity.transform)

        return entity

    def update_from(self, other: "PrefabAsset") -> None:
        """Hot-reload data and refresh all instances."""
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
        """Apply prefab data to an instance, preserving overrides."""
        from termin.visualization.core.prefab_instance_marker import PrefabInstanceMarker
        from termin.visualization.core.property_path import PropertyPath

        marker = entity.get_component(PrefabInstanceMarker)
        if marker is None:
            return

        root_data = self.root_data
        if root_data is None:
            return

        for path, value in PropertyPath.iter_from_data(root_data):
            if marker.is_overridden(path):
                continue

            if path == "name" and entity.name != root_data.get("name"):
                continue

            try:
                deserialized = self._deserialize_property_value(path, value)
                PropertyPath.set(entity, path, deserialized)
            except (KeyError, AttributeError):
                log.warning(f"[PrefabAsset] Cannot apply property path: {path}", exc_info=True)

    def _deserialize_property_value(self, path: str, value: Any) -> Any:
        """Deserialize a property value for application."""
        if isinstance(value, dict):
            if "uuid" in value:
                return self._resolve_resource_by_uuid(value["uuid"], path)
            return value

        if isinstance(value, list) and value and all(isinstance(x, (int, float)) for x in value):
            return np.array(value, dtype=np.float32)

        return value

    def _resolve_resource_by_uuid(self, uuid: str, path: str) -> Any:
        """Resolve a resource reference by UUID."""
        from termin.assets.resources import ResourceManager

        rm = ResourceManager.instance()

        path_lower = path.lower()
        if "material" in path_lower:
            return rm.get_material_by_uuid(uuid)
        if "mesh" in path_lower:
            return rm.get_mesh_by_uuid(uuid)
        if "skeleton" in path_lower:
            return rm.get_skeleton_by_uuid(uuid)

        return rm.get_asset_by_uuid(uuid)

    def _parse_content(self, content: str) -> dict | None:
        """Parse JSON content into prefab data."""
        data = json.loads(content)

        file_uuid = data.get("uuid")
        if file_uuid:
            self._uuid = file_uuid
            self._runtime_id = hash(self._uuid) & 0xFFFFFFFFFFFFFFFF
            self._has_uuid_in_spec = True

        return data

    def _on_loaded(self) -> None:
        """After loading, save file if it did not have a UUID."""
        if self._source_path is not None and self._data is not None:
            try:
                if "uuid" not in self._data:
                    self._data["uuid"] = self.uuid
                    self.save_to_file()
            except Exception:
                log.warning(f"[PrefabAsset] Failed to auto-save UUID to {self._source_path}", exc_info=True)

    def save_spec_file(self) -> bool:
        """Prefabs store UUID in the file itself, not in a spec sidecar."""
        return self.save_to_file()

    def save_to_file(self, path: str | Path | None = None) -> bool:
        """Save prefab data to a .prefab file."""
        if self._data is None:
            return False

        save_path = Path(path) if path else self._source_path
        if save_path is None:
            return False

        try:
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
        except Exception:
            log.error(f"[PrefabAsset] Failed to save to {save_path}", exc_info=True)
            return False

    @classmethod
    def from_file(cls, path: str | Path, name: str | None = None) -> "PrefabAsset":
        """Create PrefabAsset from a .prefab file."""
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
        """Create PrefabAsset from an existing Entity."""
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
