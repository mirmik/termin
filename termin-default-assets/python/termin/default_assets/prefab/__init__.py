"""Default prefab asset adapters."""

from .asset import PrefabAsset
from .asset_plugin import (
    PrefabAssetPlugin,
    PrefabImportPlugin,
    PrefabRuntimePlugin,
    create_import_plugin,
    create_runtime_plugin,
    register_prefab_asset_plugin,
    register_prefab_import_plugin,
    register_prefab_runtime_plugin,
)

__all__ = [
    "PrefabAsset",
    "PrefabAssetPlugin",
    "PrefabImportPlugin",
    "PrefabRuntimePlugin",
    "create_import_plugin",
    "create_runtime_plugin",
    "register_prefab_asset_plugin",
    "register_prefab_import_plugin",
    "register_prefab_runtime_plugin",
]
