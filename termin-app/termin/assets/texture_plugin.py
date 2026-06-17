"""Compatibility re-export for texture asset plugins."""

from termin.render.texture_plugin import (
    TextureAssetPlugin,
    TextureImportPlugin,
    TextureRuntimePlugin,
    register_texture_asset_plugin,
    register_texture_import_plugin,
    register_texture_runtime_plugin,
)

__all__ = [
    "TextureAssetPlugin",
    "TextureImportPlugin",
    "TextureRuntimePlugin",
    "register_texture_asset_plugin",
    "register_texture_import_plugin",
    "register_texture_runtime_plugin",
]
