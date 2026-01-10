"""ScenePipelineAsset - Asset for render pipeline configuration.

Stores RenderPipeline (list of passes and resource specs).
File extension: .scene_pipeline

UUID is stored inside the .scene_pipeline JSON file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from termin.assets.data_asset import DataAsset
from termin._native import log

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.pipeline import RenderPipeline


class ScenePipelineAsset(DataAsset["RenderPipeline"]):
    """
    Asset for render pipeline configuration.

    IMPORTANT: Create through ResourceManager, not directly.
    This ensures proper registration and avoids duplicates.

    Stores RenderPipeline (list of passes and their configurations).
    """

    _uses_binary = False  # JSON text format

    def __init__(
        self,
        pipeline: "RenderPipeline | None" = None,
        name: str = "pipeline",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=pipeline, name=name, source_path=source_path, uuid=uuid)
        self._target_viewports: list[str] = []

    # --- Convenience property ---

    @property
    def pipeline(self) -> "RenderPipeline | None":
        """RenderPipeline (lazy-loaded)."""
        return self.data

    @pipeline.setter
    def pipeline(self, value: "RenderPipeline | None") -> None:
        """Set pipeline and bump version."""
        self.data = value

    # --- Content parsing ---

    def _parse_content(self, content: str) -> "RenderPipeline | None":
        """Parse JSON content into RenderPipeline.

        Supports two formats:
        - Graph format (nodes, connections, viewport_frames) - compiled via nodegraph compiler
        - Pipeline format (passes, pipeline_specs) - deserialized directly
        """
        from termin.visualization.render.framegraph.pipeline import RenderPipeline
        from termin.visualization.core.resources import ResourceManager

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            log.error(f"[ScenePipelineAsset] Failed to parse JSON: {e}")
            return None

        # Detect format: graph has "nodes", pipeline has "passes"
        is_graph_format = "nodes" in data and "passes" not in data

        if is_graph_format:
            return self._compile_graph(data)
        else:
            # Pipeline format - deserialize directly
            try:
                rm = ResourceManager.instance()
                pipeline = RenderPipeline.deserialize(data, rm)
                pipeline.name = self._name
                return pipeline
            except Exception as e:
                log.error(f"[ScenePipelineAsset] Failed to deserialize pipeline: {e}")
                return None

    def _compile_graph(self, data: dict) -> "RenderPipeline | None":
        """Compile graph format data into RenderPipeline."""
        try:
            from termin.nodegraph.scene import NodeGraphScene
            from termin.nodegraph.serialization import deserialize_graph
            from termin.nodegraph.compiler import compile_graph

            # Create temporary scene and deserialize graph into it
            scene = NodeGraphScene()
            deserialize_graph(data, scene)

            # Compile to RenderPipeline
            pipeline = compile_graph(scene)
            pipeline.name = self._name

            # Store viewport names for later lookup
            viewport_frames = scene.get_viewport_frames()
            self._target_viewports = [frame.viewport_name for frame in viewport_frames]

            return pipeline
        except Exception as e:
            log.error(f"[ScenePipelineAsset] Failed to compile graph: {e}")
            return None

    @property
    def target_viewports(self) -> list[str]:
        """List of viewport names this pipeline targets (from ViewportFrames)."""
        return self._target_viewports

    def _on_loaded(self) -> None:
        """After loading, save UUID to .meta file if needed."""
        # UUID is stored in .meta file, never overwrite the pipeline file
        pass

    # --- Saving ---

    def save_to_file(self, path: Path | str | None = None) -> bool:
        """
        Save pipeline to .scene_pipeline file.

        Args:
            path: Target path. If None, uses source_path.

        Returns:
            True on success, False on failure.
        """
        target = Path(path) if path else self._source_path
        if target is None:
            log.error("[ScenePipelineAsset] No path specified for save")
            return False

        if self._data is None:
            log.error("[ScenePipelineAsset] No pipeline data to save")
            return False

        try:
            # Serialize pipeline
            data = self._data.serialize()

            # Add UUID
            data["uuid"] = self.uuid

            # Write to file
            with open(target, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Update source path and mark save time
            self._source_path = target
            self._mark_saved()

            return True

        except Exception as e:
            log.error(f"[ScenePipelineAsset] Failed to save: {e}")
            return False

    # --- Factory methods ---

    @classmethod
    def from_file(cls, path: Path | str) -> "ScenePipelineAsset":
        """
        Load ScenePipelineAsset from file.

        Args:
            path: Path to .scene_pipeline file.

        Returns:
            ScenePipelineAsset (may have pipeline=None on error).
        """
        path = Path(path)
        name = path.stem

        asset = cls(pipeline=None, name=name, source_path=path)

        # Read and parse immediately
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            asset.load_from_content(content)
        except Exception as e:
            log.error(f"[ScenePipelineAsset] Failed to load {path}: {e}")

        return asset

    @classmethod
    def from_pipeline(
        cls,
        pipeline: "RenderPipeline",
        name: str = "pipeline",
        source_path: Path | str | None = None,
    ) -> "ScenePipelineAsset":
        """
        Create ScenePipelineAsset from existing RenderPipeline.

        Args:
            pipeline: RenderPipeline instance.
            name: Asset name.
            source_path: Optional source path.

        Returns:
            ScenePipelineAsset.
        """
        asset = cls(pipeline=pipeline, name=name, source_path=source_path)
        asset._is_loaded = True
        return asset
