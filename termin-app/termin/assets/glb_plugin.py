"""Compatibility re-export for GLB asset plugins."""

from termin.glb.asset_plugin import (
    GLBAssetPlugin,
    GLBImportPlugin,
    GLBRuntimePlugin,
    create_import_plugin,
    create_runtime_plugin,
    register_glb_asset_plugin,
    register_glb_import_plugin,
    register_glb_runtime_plugin,
)

__all__ = [
    "GLBAssetPlugin",
    "GLBImportPlugin",
    "GLBRuntimePlugin",
    "create_import_plugin",
    "create_runtime_plugin",
    "register_glb_asset_plugin",
    "register_glb_import_plugin",
    "register_glb_runtime_plugin",
]
