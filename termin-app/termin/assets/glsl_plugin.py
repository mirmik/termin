"""Compatibility re-export for GLSL include asset plugins."""

from termin.render.glsl_plugin import (
    GlslAssetPlugin,
    GlslImportPlugin,
    GlslRuntimePlugin,
    register_glsl_asset_plugin,
    register_glsl_import_plugin,
    register_glsl_runtime_plugin,
)

__all__ = [
    "GlslAssetPlugin",
    "GlslImportPlugin",
    "GlslRuntimePlugin",
    "register_glsl_asset_plugin",
    "register_glsl_import_plugin",
    "register_glsl_runtime_plugin",
]
