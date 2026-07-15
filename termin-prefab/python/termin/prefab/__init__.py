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
from termin.prefab._prefab_native import (
    PrefabDocument,
    PrefabInstanceState,
    PrefabOverrideRestoreError,
    PrefabOverrideRestoreFailure,
    PrefabOverrideRestoreResult,
    PrefabOverrideValue,
    count_live_instances,
    find_live_instances,
)
from termin.prefab.property_path import PropertyPath, PropertyPathError

__all__ = [
    "PrefabAsset",
    "PrefabAssetPlugin",
    "PrefabImportPlugin",
    "PrefabDocument",
    "PrefabInstanceState",
    "PrefabOverrideRestoreError",
    "PrefabOverrideRestoreFailure",
    "PrefabOverrideRestoreResult",
    "PrefabOverrideValue",
    "PrefabRuntimePlugin",
    "PropertyPath",
    "PropertyPathError",
    "create_import_plugin",
    "create_runtime_plugin",
    "count_live_instances",
    "find_live_instances",
    "register_prefab_asset_plugin",
    "register_prefab_import_plugin",
    "register_prefab_runtime_plugin",
]
