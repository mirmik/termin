"""Shared asset-system contracts."""

from termin_assets.plugin import (
    AssetContext,
    AssetCreationPlugin,
    AssetImportPlugin,
    AssetRuntimePlugin,
    AssetTypePlugin,
    AssetTypeRegistry,
)
from termin_assets.catalog import AssetCatalog, AssetRecord
from termin_assets.plugin_discovery import (
    ASSET_IMPORT_PLUGIN_GROUP,
    ASSET_PLUGIN_GROUP,
    ASSET_RUNTIME_PLUGIN_GROUP,
    register_combined_plugins_from_entry_points,
    register_import_plugins_from_entry_points,
    register_runtime_plugins_from_entry_points,
)
from termin_assets.preload import PreLoadResult
from termin_assets.spec_file import get_uuid_from_spec, read_spec_file, write_spec_file

__all__ = [
    "ASSET_IMPORT_PLUGIN_GROUP",
    "ASSET_PLUGIN_GROUP",
    "ASSET_RUNTIME_PLUGIN_GROUP",
    "AssetCatalog",
    "AssetContext",
    "AssetCreationPlugin",
    "AssetImportPlugin",
    "AssetRecord",
    "AssetRuntimePlugin",
    "AssetTypePlugin",
    "AssetTypeRegistry",
    "PreLoadResult",
    "get_uuid_from_spec",
    "register_combined_plugins_from_entry_points",
    "register_import_plugins_from_entry_points",
    "register_runtime_plugins_from_entry_points",
    "read_spec_file",
    "write_spec_file",
]
