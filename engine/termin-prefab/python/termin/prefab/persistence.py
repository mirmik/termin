"""Canonical authoring-side file transactions for native prefab documents."""

from __future__ import annotations

import json
import os
import tempfile
import uuid as uuid_module
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tcbase import log

from termin.prefab._prefab_native import PrefabDocument

if TYPE_CHECKING:
    from termin.scene import Entity, TcScene


ROOT_ENTITY_NAME = "[Root]"


def document_from_data(data: dict[str, Any]) -> PrefabDocument:
    """Parse and validate a canonical v3 document from Python data."""
    return PrefabDocument.from_json(json.dumps(data, ensure_ascii=False))


def load_document(path: str | Path) -> PrefabDocument:
    """Read and validate a prefab without mutating the file or a scene."""
    file_path = Path(path)
    try:
        return PrefabDocument.from_json(file_path.read_text(encoding="utf-8"))
    except Exception:
        log.error(f"[PrefabPersistence] Failed to load {file_path}", exc_info=True)
        raise


def atomic_write_document(document: PrefabDocument, path: str | Path) -> None:
    """Atomically replace a prefab file after complete native validation."""
    file_path = Path(path)
    serialized = document.to_json(2)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".tmp",
            dir=str(file_path.parent),
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(serialized)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, file_path)
        temp_path = None
    except Exception:
        log.error(f"[PrefabPersistence] Failed to atomically save {file_path}", exc_info=True)
        raise
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                log.error(
                    f"[PrefabPersistence] Failed to remove temporary file {temp_path}",
                    exc_info=True,
                )


class PrefabPersistence:
    """Thin editor-facing orchestration around native PrefabDocument."""

    ROOT_ENTITY_NAME = ROOT_ENTITY_NAME

    def __init__(self, resource_manager: object | None = None):
        # Retained temporarily for call-site compatibility; document mechanics
        # do not depend on the editor resource manager.
        self._resource_manager = resource_manager

    def load(self, file_path: str | Path, scene: "TcScene") -> "Entity":
        document = load_document(file_path)
        try:
            return document.materialize_source(scene)
        except Exception:
            log.error(
                f"[PrefabPersistence] Failed to materialize {file_path}",
                exc_info=True,
            )
            raise

    def save(
        self,
        entity: "Entity",
        file_path: str | Path,
        uuid: str | None = None,
    ) -> dict[str, int]:
        file_path = Path(file_path)
        asset_uuid = uuid
        if asset_uuid is None and file_path.exists():
            asset_uuid = load_document(file_path).uuid
        if asset_uuid is None:
            asset_uuid = str(uuid_module.uuid4())

        document = PrefabDocument.capture(asset_uuid, entity)
        atomic_write_document(document, file_path)
        return {"entities": _count_entities(document.data["root"])}

    def create_empty(self, file_path: str | Path, name: str = "NewPrefab") -> str:
        del name
        asset_uuid = str(uuid_module.uuid4())
        root_source_id = str(uuid_module.uuid4())
        document = PrefabDocument.empty(
            asset_uuid,
            root_source_id,
            self.ROOT_ENTITY_NAME,
        )
        atomic_write_document(document, file_path)
        return asset_uuid


def _count_entities(root: dict[str, Any]) -> int:
    return 1 + sum(_count_entities(child) for child in root.get("children", []))
