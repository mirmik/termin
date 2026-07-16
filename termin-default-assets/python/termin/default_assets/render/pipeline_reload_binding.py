"""Session-owned integration between pipeline asset reloads and rendering."""

from __future__ import annotations

from tcbase import log
from termin_assets import AssetReloadEvent, AssetReloadSubscription


class PipelineReloadBinding:
    """Rebind pipelines in one rendering domain for one resource manager."""

    def __init__(self, resource_manager: object, rendering_manager: object) -> None:
        self._rendering_manager = rendering_manager
        self._subscription: AssetReloadSubscription | None = (
            resource_manager.subscribe_asset_reloaded(self._on_asset_reloaded)
        )

    def close(self) -> None:
        subscription = self._subscription
        if subscription is None:
            return
        self._subscription = None
        subscription.close()

    def _on_asset_reloaded(self, event: AssetReloadEvent) -> None:
        if event.type_id != "pipeline":
            return
        rebound = self._rendering_manager.recreate_render_target_pipelines_for_asset(
            event.name,
            event.uuid,
        )
        if rebound:
            log.info(
                f"[PipelineReloadBinding] Rebound {rebound} render target(s) "
                f"after reloading pipeline '{event.name}' at version {event.version}"
            )


__all__ = ["PipelineReloadBinding"]
