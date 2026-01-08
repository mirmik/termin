"""
Prefab persistence — loading and saving .prefab files.

A prefab is a reusable entity hierarchy that can be instantiated into scenes.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from termin._native import log

if TYPE_CHECKING:
    from termin.visualization.core.entity import Entity
    from termin.visualization.core.resources import ResourceManager


def _numpy_encoder(obj):
    """JSON encoder for numpy arrays."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.float32, np.float64)):
        return float(obj)
    if isinstance(obj, (np.int32, np.int64)):
        return int(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class PrefabPersistence:
    """
    Handles loading and saving of .prefab files.

    Prefab file format:
    {
        "version": "1.0",
        "root": {
            "name": "EntityName",
            "pose": {"position": [...], "rotation": [...]},
            "scale": [...],
            "components": [...],
            "children": [...]
        },
        "resources": {
            "materials": {...},
            "meshes": {...}
        }
    }
    """

    VERSION = "1.0"
    ROOT_ENTITY_NAME = "[Root]"

    def __init__(self, resource_manager: "ResourceManager"):
        self._resource_manager = resource_manager

    def save(self, entity: "Entity", file_path: str | Path, uuid: str | None = None) -> dict:
        """
        Save entity hierarchy to .prefab file.

        Args:
            entity: Root entity to save.
            file_path: Path to .prefab file.
            uuid: UUID to preserve (if None, tries to read from existing file).

        Returns:
            Stats dict with counts of saved items.
        """
        file_path = Path(file_path)

        # Preserve UUID from existing file if not provided
        if uuid is None and file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                uuid = existing_data.get("uuid")
            except Exception as e:
                log.debug(f"[PrefabPersistence] Failed to read existing UUID from {file_path}: {e}")

        # Serialize entity hierarchy
        entity_data = entity.serialize()
        if entity_data is None:
            raise ValueError(f"Entity '{entity.name}' is not serializable")

        data = {
            "version": self.VERSION,
            "root": entity_data,
        }

        # Include UUID if available
        if uuid is not None:
            data["uuid"] = uuid

        # Atomic write via temp file
        json_str = json.dumps(data, indent=2, ensure_ascii=False, default=_numpy_encoder)

        dir_path = file_path.parent
        dir_path.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".tmp", dir=str(dir_path), delete=False
        ) as f:
            f.write(json_str)
            temp_path = f.name

        os.replace(temp_path, str(file_path))

        return {
            "entities": self._count_entities(entity),
        }

    def load(self, file_path: str | Path, context=None) -> "Entity":
        """
        Load entity hierarchy from .prefab file.

        Args:
            file_path: Path to .prefab file.
            context: Optional deserialization context.

        Returns:
            Root entity of the prefab.
        """
        from termin.visualization.core.entity import Entity

        file_path = Path(file_path)

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Deserialize entity hierarchy
        root_data = data.get("root")
        if root_data is None:
            raise ValueError(f"Prefab file '{file_path}' has no root entity")

        entity = Entity.deserialize(root_data, context)
        return entity

    def create_empty(self, file_path: str | Path, name: str = "NewPrefab") -> str:
        """
        Create an empty .prefab file with a single empty entity.

        Args:
            file_path: Path to .prefab file.
            name: Ignored, root is always named "[Root]".

        Returns:
            Generated UUID for the new prefab.
        """
        import uuid as uuid_module

        file_path = Path(file_path)
        prefab_uuid = str(uuid_module.uuid4())

        data = {
            "version": self.VERSION,
            "uuid": prefab_uuid,
            "root": {
                "name": self.ROOT_ENTITY_NAME,
                "priority": 0,
                "scale": [1.0, 1.0, 1.0],
                "visible": True,
                "enabled": True,
                "pickable": True,
                "selectable": True,
                "pose": {
                    "position": [0.0, 0.0, 0.0],
                    "rotation": [0.0, 0.0, 0.0, 1.0],
                },
                "components": [],
                "children": [],
            },
        }

        json_str = json.dumps(data, indent=2, ensure_ascii=False)

        dir_path = file_path.parent
        dir_path.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".tmp", dir=str(dir_path), delete=False
        ) as f:
            f.write(json_str)
            temp_path = f.name

        os.replace(temp_path, str(file_path))

        return prefab_uuid

    def _count_entities(self, entity: "Entity") -> int:
        """Count total entities in hierarchy."""
        count = 1
        for child_transform in entity.transform.children:
            child_ent = child_transform.entity
            if child_ent is not None:
                count += self._count_entities(child_ent)
        return count
