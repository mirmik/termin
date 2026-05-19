"""Default asset plugin registration helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin_assets import AssetImportPlugin, AssetTypeRegistry


def register_default_runtime_asset_plugins(registry: "AssetTypeRegistry") -> None:
    """Register runtime-side asset plugins that have migrated off hard-coded dispatch."""
    from termin.assets.audio_clip_plugin import register_audio_clip_runtime_plugin
    from termin.assets.mesh_plugin import register_mesh_runtime_plugin
    from termin.assets.texture_plugin import register_texture_runtime_plugin

    register_audio_clip_runtime_plugin(registry)
    register_mesh_runtime_plugin(registry)
    register_texture_runtime_plugin(registry)


def register_default_import_asset_plugins(registry: "AssetTypeRegistry") -> None:
    """Register import-side asset plugins that are safe outside editor_core."""
    from termin.assets.audio_clip_plugin import register_audio_clip_import_plugin
    from termin.assets.mesh_plugin import register_mesh_import_plugin
    from termin.assets.texture_plugin import register_texture_import_plugin

    register_audio_clip_import_plugin(registry)
    register_mesh_import_plugin(registry)
    register_texture_import_plugin(registry)


def register_default_asset_plugins(registry: "AssetTypeRegistry") -> None:
    """Register both runtime and import plugins for migrated asset types."""
    register_default_runtime_asset_plugins(registry)
    register_default_import_asset_plugins(registry)


def build_import_plugin_extension_map(
    registry: "AssetTypeRegistry",
) -> dict[str, "AssetImportPlugin"]:
    """Build extension to import plugin map from a registry."""
    extension_map: dict[str, "AssetImportPlugin"] = {}
    for plugin in registry.all_import_plugins():
        for extension in plugin.extensions:
            extension_map[extension.lower()] = plugin
    return extension_map
