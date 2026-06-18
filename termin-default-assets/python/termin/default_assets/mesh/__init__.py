"""Default mesh asset adapters."""

from termin.default_assets.mesh.asset import MeshAsset
from termin.default_assets.mesh.asset_plugin import (
    MeshAssetPlugin,
    MeshImportPlugin,
    MeshRuntimePlugin,
    create_import_plugin,
    create_runtime_plugin,
    register_mesh_asset_plugin,
    register_mesh_import_plugin,
    register_mesh_runtime_plugin,
)
from termin.default_assets.mesh.mesh_spec import (
    DEFAULT_AXIS_X,
    DEFAULT_AXIS_Y,
    DEFAULT_AXIS_Z,
    MeshSpec,
)

__all__ = [
    "DEFAULT_AXIS_X",
    "DEFAULT_AXIS_Y",
    "DEFAULT_AXIS_Z",
    "MeshAsset",
    "MeshAssetPlugin",
    "MeshImportPlugin",
    "MeshRuntimePlugin",
    "MeshSpec",
    "create_import_plugin",
    "create_runtime_plugin",
    "register_mesh_asset_plugin",
    "register_mesh_import_plugin",
    "register_mesh_runtime_plugin",
]
