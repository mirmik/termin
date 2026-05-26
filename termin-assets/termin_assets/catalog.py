"""Generic external asset catalog."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class AssetRecord:
    type_id: str
    name: str
    path: str
    uuid: str
    spec_data: dict | None = None


class AssetCatalog:
    """Small project asset index for plugin-provided asset types."""

    def __init__(self) -> None:
        self.project_root: Path | None = None
        self._records_by_type: dict[str, dict[str, AssetRecord]] = {}
        self._records_by_path: dict[str, AssetRecord] = {}

    def set_project_root(self, path: str | Path | None) -> None:
        self.project_root = Path(path).resolve() if path is not None else None

    def upsert(self, record: AssetRecord) -> None:
        by_uuid = self._records_by_type.setdefault(record.type_id, {})
        old = by_uuid.get(record.uuid)
        if old is not None:
            self._records_by_path.pop(old.path, None)
        by_uuid[record.uuid] = record
        self._records_by_path[record.path] = record

    def remove_path(self, path: str) -> None:
        record = self._records_by_path.pop(path, None)
        if record is None:
            return
        by_uuid = self._records_by_type.get(record.type_id)
        if by_uuid is not None:
            by_uuid.pop(record.uuid, None)

    def list_names(self, type_id: str) -> list[str]:
        records = self._records_by_type.get(type_id, {})
        return sorted(record.name for record in records.values())

    def get_by_name(self, type_id: str, name: str) -> AssetRecord | None:
        records = self._records_by_type.get(type_id, {})
        for record in records.values():
            if record.name == name:
                return record
        return None

    def get_by_uuid(self, type_id: str, uuid: str) -> AssetRecord | None:
        return self._records_by_type.get(type_id, {}).get(uuid)

    def find_uuid_by_name(self, type_id: str, name: str) -> str | None:
        record = self.get_by_name(type_id, name)
        return record.uuid if record is not None else None

    def has_type(self, type_id: str) -> bool:
        return type_id in self._records_by_type

