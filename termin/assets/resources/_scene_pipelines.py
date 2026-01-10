"""Scene pipelines mixin for ResourceManager."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.pipeline import RenderPipeline
    from termin.assets.scene_pipeline_asset import ScenePipelineAsset


class ScenePipelinesMixin:
    """Mixin for scene pipeline management (.scene_pipeline files)."""

    def register_scene_pipeline(
        self,
        name: str,
        pipeline: "RenderPipeline",
        source_path: str | None = None,
        uuid: str | None = None,
    ) -> "ScenePipelineAsset":
        """
        Register a RenderPipeline as a scene pipeline.

        Args:
            name: Pipeline name.
            pipeline: RenderPipeline instance.
            source_path: Optional path to .scene_pipeline file.
            uuid: Optional UUID.

        Returns:
            ScenePipelineAsset.
        """
        from termin.assets.scene_pipeline_asset import ScenePipelineAsset

        # Check if already exists
        asset = self._scene_pipeline_registry.get_asset(name)
        if asset is not None:
            # Update existing asset
            asset._data = pipeline
            asset._bump_version()
            return asset

        # Create new asset
        asset = ScenePipelineAsset.from_pipeline(pipeline, name=name, source_path=source_path)
        if uuid:
            asset._uuid = uuid
        self._scene_pipeline_registry.register(name, asset, source_path=source_path, uuid=asset.uuid)
        return asset

    def get_scene_pipeline(self, name: str) -> Optional["RenderPipeline"]:
        """
        Get a copy of RenderPipeline by name.

        Pipelines are mutable, so we return a copy.

        Args:
            name: Pipeline name.

        Returns:
            Copy of RenderPipeline or None if not found.
        """
        pipeline = self._scene_pipeline_registry.get(name)
        if pipeline is not None:
            return pipeline.copy()
        return None

    def get_scene_pipeline_asset(self, name: str) -> Optional["ScenePipelineAsset"]:
        """
        Get ScenePipelineAsset by name.

        Args:
            name: Pipeline name.

        Returns:
            ScenePipelineAsset or None if not found.
        """
        return self._scene_pipeline_registry.get_asset(name)

    def get_scene_pipeline_by_uuid(self, uuid: str) -> Optional["RenderPipeline"]:
        """
        Get a copy of RenderPipeline by UUID.

        Args:
            uuid: Pipeline UUID.

        Returns:
            Copy of RenderPipeline or None if not found.
        """
        asset = self._scene_pipeline_registry.get_asset_by_uuid(uuid)
        if asset is not None:
            pipeline = asset.data
            if pipeline is not None:
                return pipeline.copy()
        return None

    def get_scene_pipeline_asset_by_uuid(self, uuid: str) -> Optional["ScenePipelineAsset"]:
        """
        Get ScenePipelineAsset by UUID.

        Args:
            uuid: Pipeline UUID.

        Returns:
            ScenePipelineAsset or None if not found.
        """
        return self._scene_pipeline_registry.get_asset_by_uuid(uuid)

    def list_scene_pipeline_names(self) -> list[str]:
        """
        List all registered scene pipeline names.

        Returns:
            Sorted list of pipeline names.
        """
        return sorted(self._scene_pipeline_registry.list_names())
