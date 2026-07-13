"""Asset type plugin contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from termin_assets.preload import PreLoadResult


@dataclass(frozen=True)
class AssetContext:
    """Context passed from an asset manager to asset plugins."""

    resource_manager: object
    name: str


class AssetRuntimePlugin(Protocol):
    """Runtime-side plugin for asset registration and hot reload."""

    type_id: str

    def register(self, context: AssetContext, result: "PreLoadResult") -> None:
        ...

    def reload(self, context: AssetContext, result: "PreLoadResult") -> bool | None:
        ...


@runtime_checkable
class AssetRuntimeUnregisterPlugin(Protocol):
    """Optional runtime-side plugin support for removing file-backed assets."""

    type_id: str

    def unregister(self, context: AssetContext, result: "PreLoadResult") -> None:
        ...


class AssetImportPlugin(Protocol):
    """Editor/import-side plugin for turning files into preload results."""

    type_id: str
    extensions: set[str]
    priority: int

    def preload(self, path: str) -> "PreLoadResult | None":
        ...


@runtime_checkable
class AssetCreationPlugin(Protocol):
    """Optional plugin capability for creating a new project asset file."""

    type_id: str

    def create_asset(self, project_root: str, name: str) -> "PreLoadResult":
        ...


class AssetTypePlugin(AssetRuntimePlugin, AssetImportPlugin, Protocol):
    """Compatibility protocol for plugins that currently implement both sides."""


class AssetTypeRegistry:
    """Registry of runtime and import asset plugins."""

    def __init__(self) -> None:
        self._runtime_by_type: dict[str, AssetRuntimePlugin] = {}
        self._import_by_type: dict[str, AssetImportPlugin] = {}
        self._import_by_extension: dict[str, list[AssetImportPlugin]] = {}

    def register(self, plugin: AssetTypePlugin) -> None:
        """Register a combined plugin on both runtime and import sides."""
        self.register_runtime(plugin)
        self.register_import(plugin)

    def register_runtime(self, plugin: AssetRuntimePlugin) -> None:
        self._runtime_by_type[plugin.type_id] = plugin

    def register_import(self, plugin: AssetImportPlugin) -> None:
        previous = self._import_by_type.get(plugin.type_id)
        if previous is not None:
            for extension_plugins in self._import_by_extension.values():
                extension_plugins[:] = [
                    item for item in extension_plugins if item.type_id != plugin.type_id
                ]

        self._import_by_type[plugin.type_id] = plugin
        for ext in plugin.extensions:
            normalized = ext.lower()
            plugins = self._import_by_extension.setdefault(normalized, [])
            plugins.append(plugin)
            plugins.sort(key=lambda item: item.priority)

    def get(self, type_id: str) -> AssetTypePlugin | None:
        """Compatibility alias for runtime plugin lookup."""
        plugin = self._runtime_by_type.get(type_id)
        return plugin

    def get_runtime(self, type_id: str) -> AssetRuntimePlugin | None:
        return self._runtime_by_type.get(type_id)

    def get_import(self, type_id: str) -> AssetImportPlugin | None:
        return self._import_by_type.get(type_id)

    def get_for_extension(self, extension: str) -> list[AssetImportPlugin]:
        return list(self._import_by_extension.get(extension.lower(), []))

    def all_runtime_plugins(self) -> list[AssetRuntimePlugin]:
        return list(self._runtime_by_type.values())

    def all_import_plugins(self) -> list[AssetImportPlugin]:
        return list(self._import_by_type.values())

    def all_plugins(self) -> list[AssetRuntimePlugin]:
        """Compatibility alias for runtime plugins."""
        return self.all_runtime_plugins()
