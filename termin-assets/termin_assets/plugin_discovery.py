"""Entry point discovery for external asset plugins."""

from __future__ import annotations

from importlib.metadata import entry_points
import logging

from termin_assets.plugin import AssetTypeRegistry


logger = logging.getLogger(__name__)

ASSET_IMPORT_PLUGIN_GROUP = "termin.asset_import_plugins"
ASSET_RUNTIME_PLUGIN_GROUP = "termin.asset_runtime_plugins"
ASSET_PLUGIN_GROUP = "termin.asset_plugins"


def register_import_plugins_from_entry_points(
    registry: AssetTypeRegistry,
    group: str = ASSET_IMPORT_PLUGIN_GROUP,
) -> None:
    """Load and register import-side asset plugins from package entry points."""
    for plugin in _load_plugins(group):
        registry.register_import(plugin)


def register_runtime_plugins_from_entry_points(
    registry: AssetTypeRegistry,
    group: str = ASSET_RUNTIME_PLUGIN_GROUP,
) -> None:
    """Load and register runtime-side asset plugins from package entry points."""
    for plugin in _load_plugins(group):
        registry.register_runtime(plugin)


def register_combined_plugins_from_entry_points(
    registry: AssetTypeRegistry,
    group: str = ASSET_PLUGIN_GROUP,
) -> None:
    """Load and register combined asset plugins from package entry points."""
    for plugin in _load_plugins(group):
        registry.register(plugin)


def _load_plugins(group: str) -> list[object]:
    plugins: list[object] = []
    for entry_point in entry_points(group=group):
        try:
            factory = entry_point.load()
            plugin = factory()
            plugins.append(plugin)
        except Exception:
            logger.error(
                "Failed to load asset plugin entry point %s from group %s",
                entry_point.name,
                group,
                exc_info=True,
            )
    return plugins

