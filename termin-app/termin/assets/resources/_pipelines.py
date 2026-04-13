"""Pipelines mixin for ResourceManager."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.pipeline import RenderPipeline
    from termin.assets.pipeline_asset import PipelineAsset


class PipelinesMixin:
    """Mixin for pipeline management."""

    def register_pipeline(self, name: str, pipeline: "RenderPipeline", uuid: str | None = None):
        """Register a RenderPipeline by name."""
        from termin.assets.pipeline_asset import PipelineAsset

        # Check if already exists
        asset = self._pipeline_registry.get_asset(name)
        if asset is not None:
            # Update existing asset
            asset._data = pipeline
            return

        # Create new asset
        asset = PipelineAsset.from_pipeline(pipeline, name=name, uuid=uuid)
        self._pipeline_registry.register(name, asset, uuid=uuid)

    def get_pipeline(self, name: str) -> Optional["RenderPipeline"]:
        """Get a copy of RenderPipeline by name (pipelines are mutable)."""
        pipeline = self._pipeline_registry.get(name)
        if pipeline is not None:
            return pipeline.copy(self)
        return None

    def get_pipeline_asset(self, name: str) -> Optional["PipelineAsset"]:
        """Get PipelineAsset by name."""
        return self._pipeline_registry.get_asset(name)

    def get_pipeline_by_uuid(self, uuid: str) -> Optional["RenderPipeline"]:
        """Get a copy of RenderPipeline by UUID."""
        asset = self._pipeline_registry.get_asset_by_uuid(uuid)
        if asset is not None:
            pipeline = asset.data
            if pipeline is not None:
                return pipeline.copy(self)
        return None

    def list_pipeline_names(self) -> list[str]:
        """List all registered pipeline names."""
        return sorted(self._pipeline_registry.list_names())
