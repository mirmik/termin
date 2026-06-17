"""Default asset plugin composition helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin_assets.plugin_discovery import (
    register_combined_plugins_from_entry_points,
    register_import_plugins_from_entry_points,
    register_runtime_plugins_from_entry_points,
)

if TYPE_CHECKING:
    from termin_assets.plugin import AssetImportPlugin, AssetTypeRegistry


def register_default_runtime_asset_plugins(registry: "AssetTypeRegistry") -> None:
    """Register runtime-side asset plugins declared by installed packages."""
    register_runtime_plugins_from_entry_points(registry)
    register_combined_plugins_from_entry_points(registry)


def register_default_import_asset_plugins(registry: "AssetTypeRegistry") -> None:
    """Register import-side asset plugins declared by installed packages."""
    register_import_plugins_from_entry_points(registry)
    register_combined_plugins_from_entry_points(registry)


def register_default_asset_plugins(registry: "AssetTypeRegistry") -> None:
    """Register both runtime and import plugins declared by installed packages."""
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
