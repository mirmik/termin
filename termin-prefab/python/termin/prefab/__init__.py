"""Prefab runtime and asset integration."""

from termin.prefab.asset import PrefabAsset
from termin.prefab.asset_plugin import (
    PrefabAssetPlugin,
    PrefabImportPlugin,
    PrefabRuntimePlugin,
    create_import_plugin,
    create_runtime_plugin,
    register_prefab_asset_plugin,
    register_prefab_import_plugin,
    register_prefab_runtime_plugin,
)
from termin.prefab.instance_marker import PrefabInstanceMarker
from termin.prefab.property_path import PropertyPath, PropertyPathError
from termin.prefab.registry import PrefabRegistry

__all__ = [
    "PrefabAsset",
    "PrefabAssetPlugin",
    "PrefabImportPlugin",
    "PrefabInstanceMarker",
    "PrefabRegistry",
    "PrefabRuntimePlugin",
    "PropertyPath",
    "PropertyPathError",
    "create_import_plugin",
    "create_runtime_plugin",
    "register_prefab_asset_plugin",
    "register_prefab_import_plugin",
    "register_prefab_runtime_plugin",
]
