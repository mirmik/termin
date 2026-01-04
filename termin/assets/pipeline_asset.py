"""PipelineAsset - Asset for render pipelines."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from termin.assets.data_asset import DataAsset

if TYPE_CHECKING:
    from termin.visualization.render.framegraph import RenderPipeline


class PipelineAsset(DataAsset["RenderPipeline"]):
    """
    Asset for render pipelines (.pipeline files).

    IMPORTANT: Create through ResourceManager, not directly.

    Example:
        rm = ResourceManager.instance()
        pipeline = rm.get_pipeline("my_pipeline")
        asset = rm.get_pipeline_asset("my_pipeline")
    """

    _uses_binary = False  # JSON text files

    def __init__(
        self,
        data: "RenderPipeline | None" = None,
        name: str = "pipeline",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        """
        Initialize PipelineAsset.

        Args:
            data: RenderPipeline instance (can be None for lazy loading)
            name: Pipeline name
            source_path: Path to .pipeline file
            uuid: Existing UUID or None to generate new one
        """
        super().__init__(data=data, name=name, source_path=source_path, uuid=uuid)

    @property
    def pipeline(self) -> "RenderPipeline | None":
        """Get the render pipeline (lazy-loaded)."""
        return self.data

    def _parse_content(self, content: str) -> "RenderPipeline | None":
        """Parse JSON content into RenderPipeline."""
        from termin.assets.resources import ResourceManager
        from termin.visualization.render.framegraph.pipeline import RenderPipeline

        data = json.loads(content)
        rm = ResourceManager.instance()
        return RenderPipeline.deserialize(data, rm)

    @classmethod
    def from_pipeline(
        cls,
        pipeline: "RenderPipeline",
        name: str | None = None,
        uuid: str | None = None,
    ) -> "PipelineAsset":
        """
        Create PipelineAsset from existing RenderPipeline.

        Args:
            pipeline: RenderPipeline instance
            name: Asset name (defaults to pipeline.name)
            uuid: Optional fixed UUID

        Returns:
            PipelineAsset wrapping the pipeline
        """
        return cls(
            data=pipeline,
            name=name or pipeline.name,
            uuid=uuid,
        )
