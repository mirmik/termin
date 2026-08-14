"""Default navmesh asset adapters."""

from termin.default_assets.navmesh.asset import DetourNavMeshData, DetourNavMeshTileData, NavMeshAsset
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
from termin.default_assets.navmesh.handle import NavMeshHandle

__all__ = [
    "DetourNavMeshData",
    "DetourNavMeshTileData",
    "NavMeshAsset",
    "NavMeshAssetPlugin",
    "NavMeshHandle",
    "NavMeshImportPlugin",
    "NavMeshRuntimePlugin",
    "create_import_plugin",
    "create_runtime_plugin",
    "register_navmesh_asset_plugin",
    "register_navmesh_import_plugin",
    "register_navmesh_runtime_plugin",
]
