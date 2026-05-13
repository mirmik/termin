"""Shared asset-system contracts."""

from termin_assets.plugin import (
    AssetContext,
    AssetImportPlugin,
    AssetRuntimePlugin,
    AssetTypePlugin,
    AssetTypeRegistry,
)
from termin_assets.preload import PreLoadResult
from termin_assets.spec_file import get_uuid_from_spec, read_spec_file, write_spec_file

__all__ = [
    "AssetContext",
    "AssetImportPlugin",
    "AssetRuntimePlugin",
    "AssetTypePlugin",
    "AssetTypeRegistry",
    "PreLoadResult",
    "get_uuid_from_spec",
    "read_spec_file",
    "write_spec_file",
]
