"""Shared asset-system contracts."""

from termin_assets.asset import Asset
from termin_assets.asset_registry import AssetRegistry
from termin_assets.data_asset import DataAsset
from termin_assets.identifiable import Identifiable
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
from termin_assets.default_plugins import (
    build_import_plugin_extension_map,
    register_default_asset_plugins,
    register_default_import_asset_plugins,
    register_default_runtime_asset_plugins,
)
from termin_assets.preload import PreLoadResult
from termin_assets.plugin_preloader import PluginPreLoader
from termin_assets.project_file_watcher import FilePreLoader, ProjectFileWatcher
from termin_assets.resource_handle import (
    ResourceHandle,
    get_resource_manager,
    set_resource_manager_factory,
)
from termin_assets.resource_manager import AssetRuntimeManager
from termin_assets.spec_file import get_uuid_from_spec, read_spec_file, write_spec_file

__all__ = [
    "ASSET_IMPORT_PLUGIN_GROUP",
    "ASSET_PLUGIN_GROUP",
    "ASSET_RUNTIME_PLUGIN_GROUP",
    "AssetCatalog",
    "AssetContext",
    "AssetCreationPlugin",
    "AssetImportPlugin",
    "Asset",
    "AssetRegistry",
    "AssetRecord",
    "AssetRuntimePlugin",
    "AssetRuntimeManager",
    "AssetTypePlugin",
    "AssetTypeRegistry",
    "build_import_plugin_extension_map",
    "DataAsset",
    "Identifiable",
    "PreLoadResult",
    "FilePreLoader",
    "PluginPreLoader",
    "ProjectFileWatcher",
    "ResourceHandle",
    "get_uuid_from_spec",
    "get_resource_manager",
    "register_combined_plugins_from_entry_points",
    "register_default_asset_plugins",
    "register_default_import_asset_plugins",
    "register_default_runtime_asset_plugins",
    "register_import_plugins_from_entry_points",
    "register_runtime_plugins_from_entry_points",
    "read_spec_file",
    "set_resource_manager_factory",
    "write_spec_file",
]
