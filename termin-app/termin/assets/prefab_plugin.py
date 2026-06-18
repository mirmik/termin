"""Compatibility re-export for prefab asset plugins.

Canonical module: :mod:`termin.prefab.asset_plugin`.
"""

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

__all__ = [
    "PrefabAssetPlugin",
    "PrefabImportPlugin",
    "PrefabRuntimePlugin",
    "create_import_plugin",
    "create_runtime_plugin",
    "register_prefab_asset_plugin",
    "register_prefab_import_plugin",
    "register_prefab_runtime_plugin",
]
