from __future__ import annotations

from types import SimpleNamespace

from termin.default_assets.render.pipeline_reload_binding import PipelineReloadBinding
from termin_assets import AssetReloadEvent


class _Subscription:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _ResourceManager:
    def __init__(self) -> None:
        self.callback = None
        self.subscription = _Subscription()

    def subscribe_asset_reloaded(self, callback):
        self.callback = callback
        return self.subscription


def test_pipeline_reload_binding_filters_events_and_has_explicit_lifetime() -> None:
    resource_manager = _ResourceManager()
    calls = []
    rendering_manager = SimpleNamespace(
        recreate_render_target_pipelines_for_asset=lambda name, uuid: calls.append((name, uuid)) or 2
    )
    binding = PipelineReloadBinding(resource_manager, rendering_manager)

    resource_manager.callback(AssetReloadEvent("material", "surface", "material-uuid", 3))
    resource_manager.callback(AssetReloadEvent("pipeline", "post", "pipeline-uuid", 4))

    assert calls == [("post", "pipeline-uuid")]
    binding.close()
    assert resource_manager.subscription.closed
    binding.close()
