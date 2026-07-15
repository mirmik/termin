"""PrefabAsset - asset for reusable entity hierarchies."""

from __future__ import annotations

import uuid as uuid_module
from pathlib import Path
from typing import Any, Protocol, TYPE_CHECKING, cast

import numpy as np

from tcbase import log
from termin_assets import DataAsset, get_resource_manager

if TYPE_CHECKING:
    from termin.scene import Entity, GeneralTransform3, TcScene


class PrefabResourceManager(Protocol):
    """Resource-manager surface needed by prefab runtime resolution."""

    def get_material_by_uuid(self, uuid: str) -> Any:
        ...

    def get_mesh_by_uuid(self, uuid: str) -> Any:
        ...

    def get_skeleton_by_uuid(self, uuid: str) -> Any:
        ...

    def get_asset_by_uuid(self, uuid: str) -> Any:
        ...


class PrefabAsset(DataAsset[dict]):
    """Asset for .prefab files."""

    VERSION = "3.0"
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
        scene: "TcScene | None" = None,
        parent: "GeneralTransform3 | None" = None,
        position: tuple[float, float, float] | None = None,
        name: str | None = None,
    ) -> "Entity":
        """Create an instance of this prefab."""
        self.ensure_loaded()

        root_data = self.root_data
        if root_data is None:
            raise ValueError(f"Prefab '{self.name}' has no root data")

        parent_entity = parent.entity if parent is not None else None
        target_scene = scene
        if target_scene is None and parent_entity is not None:
            target_scene = parent_entity.scene
        if target_scene is None:
            raise ValueError(f"Prefab '{self.name}' requires an explicit target scene")

        from termin.prefab._prefab_native import instantiate_document
        from termin.prefab.persistence import document_from_data

        try:
            document = document_from_data(self._data)
            entity = instantiate_document(
                document,
                target_scene,
                parent_entity,
                name,
                position,
            )
        except Exception as exc:
            log.error(
                f"[PrefabAsset] Failed to instantiate prefab '{self.name}': {exc}",
                exc_info=True,
            )
            raise RuntimeError(f"Failed to instantiate prefab '{self.name}': {exc}") from exc

        return entity

    def update_from(self, other: "PrefabAsset") -> None:
        """Hot-reload data and refresh all instances."""
        self._data = other._data
        self._bump_version()
        self._update_all_instances()

    def _update_all_instances(self) -> None:
        """Update all instances of this prefab."""
        from termin.prefab._prefab_native import PrefabInstanceState, find_live_instances
        from termin.prefab.persistence import document_from_data

        if self._data is None:
            log.error(f"[PrefabAsset] Cannot update instances of unloaded prefab '{self.name}'")
            return

        source_revision = document_from_data(self._data).source_revision
        instances = find_live_instances(self.uuid)
        for entity in instances:
            if entity.valid():
                self.apply_to_instance(entity)
                state = entity.get_component(PrefabInstanceState)
                if state is not None:
                    state.source_revision = source_revision

    def apply_to_instance(self, entity: "Entity") -> None:
        """Apply prefab data to an instance, preserving overrides."""
        from termin.prefab.property_path import PropertyPath, PropertyPathError

        from termin.prefab._prefab_native import PrefabInstanceState

        state = entity.get_component(PrefabInstanceState)
        if state is None:
            return

        root_data = self.root_data
        if root_data is None:
            return

        for path, value in PropertyPath.iter_from_data(root_data):
            if path == "name" and entity.name != root_data.get("name"):
                continue

            try:
                deserialized = self._deserialize_property_value(path, value)
                PropertyPath.set_or_raise(entity, path, deserialized)
            except PropertyPathError:
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
        resource_manager = get_resource_manager()
        if resource_manager is None:
            log.error("[PrefabAsset] Resource manager factory is not configured")
            return None
        rm = cast(PrefabResourceManager, resource_manager)

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
        from termin.prefab._prefab_native import PrefabDocument

        document = PrefabDocument.from_json(content)
        data = document.data

        file_uuid = data.get("uuid")
        if file_uuid:
            self._uuid = file_uuid
            self._runtime_id = hash(self._uuid) & 0xFFFFFFFFFFFFFFFF
            self._has_uuid_in_spec = True

        return data

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
            from termin.prefab.persistence import atomic_write_document, document_from_data

            document = document_from_data(self._data)
            atomic_write_document(document, save_path)

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

        from termin.prefab.persistence import load_document

        document = load_document(path)
        data = document.data

        return cls(
            data=data,
            name=name or path.stem,
            source_path=path,
            uuid=document.uuid,
        )

    @classmethod
    def from_entity(
        cls,
        entity: "Entity",
        name: str | None = None,
        source_path: str | Path | None = None,
    ) -> "PrefabAsset":
        """Create PrefabAsset from an existing Entity."""
        from termin.prefab._prefab_native import PrefabDocument

        asset_uuid = str(uuid_module.uuid4())
        document = PrefabDocument.capture(asset_uuid, entity)

        return cls(
            data=document.data,
            name=name or entity.name,
            source_path=source_path,
            uuid=asset_uuid,
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
