"""PreLoadResult-based file registration dispatch."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from tcbase import log
from termin_assets import AssetContext

if TYPE_CHECKING:
    from termin_assets import PreLoadResult


class RegistrationMixin:
    """Dispatch file registration and reload to runtime asset plugins."""

    def register_file(self, result: "PreLoadResult") -> None:
        name = self._resource_name_from_preload_result(result)
        plugin = self._asset_type_plugins.get_runtime(result.resource_type)
        if plugin is None:
            log.error(f"[ResourceManager] No runtime asset plugin registered for type: {result.resource_type}")
            return

        plugin.register(AssetContext(resource_manager=self, name=name), result)

    def reload_file(self, result: "PreLoadResult") -> None:
        name = self._resource_name_from_preload_result(result)
        plugin = self._asset_type_plugins.get_runtime(result.resource_type)
        if plugin is None:
            log.error(f"[ResourceManager] No runtime asset plugin registered for reload type: {result.resource_type}")
            return

        plugin.reload(AssetContext(resource_manager=self, name=name), result)

    def _resource_name_from_preload_result(self, result: "PreLoadResult") -> str:
        if result.resource_type == "glsl":
            return os.path.basename(result.path)
        return os.path.splitext(os.path.basename(result.path))[0]
