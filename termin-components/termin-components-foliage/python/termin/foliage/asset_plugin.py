"""Foliage data asset import contract.

The .tfoliage payload is parsed by native code in termin-components-foliage.
This module only describes the project-file sidecar metadata and import plugin
used by editors/build tools.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from tcbase import log
from termin_assets import AssetRecord, PreLoadResult, read_spec_file, write_spec_file

if TYPE_CHECKING:
    from termin_assets import AssetTypeRegistry


FOLIAGE_DATA_TYPE_ID = "foliage_data"
FOLIAGE_DATA_FORMAT = "termin.foliage"
FOLIAGE_DATA_FORMAT_VERSION = 1


def build_foliage_meta(uuid: str) -> dict:
    return {
        "uuid": uuid,
        "type": FOLIAGE_DATA_TYPE_ID,
        "format": FOLIAGE_DATA_FORMAT,
        "format_version": FOLIAGE_DATA_FORMAT_VERSION,
    }


class FoliageDataImportPlugin:
    """Import-side plugin for .tfoliage binary placement payloads."""

    type_id = FOLIAGE_DATA_TYPE_ID
    extensions = {".tfoliage"}
    priority = 10

    def preload(self, path: str) -> PreLoadResult:
        spec_data = read_spec_file(path)
        uuid = spec_data.get("uuid") if spec_data else None
        return PreLoadResult(
            resource_type=self.type_id,
            path=path,
            content=None,
            uuid=uuid,
            spec_data=spec_data,
        )

    def create_asset(self, project_root: str, name: str) -> PreLoadResult:
        safe_name = _safe_asset_name(name)
        uuid = str(uuid4())
        path = Path(project_root) / "Assets" / "Foliage" / f"{safe_name}.tfoliage"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(f"Foliage asset already exists: {path}")
        _write_empty_foliage_file(path)
        spec_data = build_foliage_meta(uuid)
        if not write_spec_file(str(path), spec_data):
            raise RuntimeError(f"Failed to write foliage asset meta: {path}")
        return PreLoadResult(
            resource_type=self.type_id,
            path=str(path),
            content=None,
            uuid=uuid,
            spec_data=spec_data,
        )


class FoliageDataRuntimePlugin:
    """Runtime-side editor catalog registration for foliage data assets."""

    type_id = FOLIAGE_DATA_TYPE_ID

    def register(self, context, result: PreLoadResult) -> None:
        if not result.uuid:
            log.error(f"[FoliageDataRuntimePlugin] cannot register foliage asset without uuid: {result.path}")
            return
        handle = _declare_native_foliage_data(result.uuid, context.name, result.path)
        if not handle.is_valid:
            log.error(f"[FoliageDataRuntimePlugin] failed to declare native foliage asset: {result.uuid}")
            return
        context.resource_manager.external_assets.upsert(
            AssetRecord(
                type_id=self.type_id,
                name=context.name,
                path=result.path,
                uuid=result.uuid,
                spec_data=result.spec_data,
            )
        )

    def reload(self, context, result: PreLoadResult) -> None:
        self.register(context, result)

    def unregister(self, context, result: PreLoadResult) -> None:
        context.resource_manager.external_assets.remove_path(result.path)


def _declare_native_foliage_data(uuid: str, name: str, path: str):
    from termin.foliage import TcFoliageData

    return TcFoliageData.declare(uuid, name, path)


def create_import_plugin() -> FoliageDataImportPlugin:
    return FoliageDataImportPlugin()


def create_runtime_plugin() -> FoliageDataRuntimePlugin:
    return FoliageDataRuntimePlugin()


def register_foliage_data_import_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_import(FoliageDataImportPlugin())


def _safe_asset_name(name: str) -> str:
    result = []
    for ch in name.strip():
        if ch.isalnum() or ch in ("_", "-"):
            result.append(ch)
        elif ch.isspace():
            result.append("_")
    safe = "".join(result).strip("_")
    return safe or "foliage"


def _write_empty_foliage_file(path: Path) -> None:
    # Header layout mirrors FoliageFileHeader v1 in native foliage_file.cpp.
    import struct

    magic = b"TFOLIAGE"
    version = 1
    header_size = 96
    instance_stride = 40
    flags = 0
    coordinate_space_local = 1
    reserved0 = 0
    instance_count = 0
    bounds_min = (0.0, 0.0, 0.0)
    bounds_max = (0.0, 0.0, 0.0)
    reserved = bytes(32)
    header = struct.pack(
        "<8sIIIIIIQffffff32s",
        magic,
        version,
        header_size,
        instance_stride,
        flags,
        coordinate_space_local,
        reserved0,
        instance_count,
        *bounds_min,
        *bounds_max,
        reserved,
    )
    path.write_bytes(header)
