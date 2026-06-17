"""Adapter from asset import plugins to ProjectFileWatcher FilePreLoader."""

from __future__ import annotations

from collections.abc import Callable

from termin_assets.plugin import AssetImportPlugin
from termin_assets.preload import PreLoadResult
from termin_assets.project_file_watcher import FilePreLoader


class PluginPreLoader(FilePreLoader):
    """Expose an AssetImportPlugin through the current watcher preloader API."""

    def __init__(
        self,
        plugin: AssetImportPlugin,
        resource_manager: object,
        on_resource_reloaded: Callable[[str, str], None] | None = None,
    ) -> None:
        super().__init__(resource_manager, on_resource_reloaded)
        self._plugin = plugin

    @property
    def priority(self) -> int:
        return self._plugin.priority

    @property
    def extensions(self) -> set[str]:
        return self._plugin.extensions

    @property
    def resource_type(self) -> str:
        return self._plugin.type_id

    def preload(self, path: str) -> PreLoadResult | None:
        return self._plugin.preload(path)

    def on_file_removed(self, path: str) -> None:
        self._resource_manager.external_assets.remove_path(path)
        super().on_file_removed(path)
