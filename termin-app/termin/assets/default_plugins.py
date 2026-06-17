"""Compatibility re-export for default asset plugin helpers."""

from __future__ import annotations

from termin_assets.default_plugins import (
    build_import_plugin_extension_map,
    register_default_asset_plugins,
    register_default_import_asset_plugins,
    register_default_runtime_asset_plugins,
)

__all__ = [
    "build_import_plugin_extension_map",
    "register_default_asset_plugins",
    "register_default_import_asset_plugins",
    "register_default_runtime_asset_plugins",
]
