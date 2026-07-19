"""Adapter from asset import plugins to ProjectFileWatcher FilePreLoader."""

from __future__ import annotations

from collections.abc import Callable

from tcbase import log

from termin_assets.plugin import AssetImportPlugin
from termin_assets.preload import AssetIdentityPolicy, PreLoadResult
from termin_assets.project_file_watcher import FilePreLoader
from termin_assets.spec_file import ensure_uuid_in_spec


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
        result = self._plugin.preload(path)
        if result is None or result.identity_policy is AssetIdentityPolicy.REQUIRE_EXISTING:
            return result

        identity = ensure_uuid_in_spec(path)
        if identity is None:
            log.error(f"[PluginPreLoader] Failed to assign persistent UUID: {path}")
            return None
        persistent_uuid, spec_data = identity
        if result.uuid is not None and result.uuid != persistent_uuid:
            log.error(
                "[PluginPreLoader] Import UUID does not match persistent metadata: "
                f"{path} (import={result.uuid!r}, metadata={persistent_uuid!r})"
            )
            return None
        result.uuid = persistent_uuid
        result.spec_data = spec_data
        return result
