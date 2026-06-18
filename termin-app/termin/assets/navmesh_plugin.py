"""Compatibility re-export for navmesh asset plugins.

Canonical implementation lives in :mod:`termin.default_assets.navmesh.asset_plugin`.
"""

from termin.default_assets.navmesh.asset_plugin import (
    NavMeshAssetPlugin,
    NavMeshImportPlugin,
    NavMeshRuntimePlugin,
    create_import_plugin,
    create_runtime_plugin,
    register_navmesh_asset_plugin,
    register_navmesh_import_plugin,
    register_navmesh_runtime_plugin,
)

__all__ = [
    "NavMeshAssetPlugin",
    "NavMeshImportPlugin",
    "NavMeshRuntimePlugin",
    "create_import_plugin",
    "create_runtime_plugin",
    "register_navmesh_asset_plugin",
    "register_navmesh_import_plugin",
    "register_navmesh_runtime_plugin",
]
