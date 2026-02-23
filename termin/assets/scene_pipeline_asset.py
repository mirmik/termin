"""ScenePipelineAsset - Asset for render pipeline configuration.

Stores pipeline graph source (nodes, connections) via TcScenePipelineTemplate (C).
Compilation to RenderPipeline happens on demand via compile().
File extension: .scene_pipeline

UUID is stored inside the .scene_pipeline JSON file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from termin.assets.asset import Asset
from tcbase import log
from termin._native.render import TcScenePipelineTemplate

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.pipeline import RenderPipeline


class ScenePipelineAsset(Asset):
    """
    Asset for render pipeline configuration.

    IMPORTANT: Create through ResourceManager, not directly.
    This ensures proper registration and avoids duplicates.

    Stores pipeline graph source (nodes, connections) in C template.
    Call compile() to get RenderPipeline.
    """

    _template: TcScenePipelineTemplate

    def __init__(
        self,
        graph_data: dict | None = None,
        name: str = "pipeline",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(name=name, source_path=source_path, uuid=uuid)

        # Declare C template with uuid/name
        self._template = TcScenePipelineTemplate.declare(self.uuid, name)

        # If graph_data provided, set it
        if graph_data is not None:
            self._template.set_graph_data(graph_data)
            self._loaded = True

    # --- Template access ---

    @property
    def template(self) -> TcScenePipelineTemplate:
        """Get underlying C template."""
        return self._template

    # --- Graph data property ---

    @property
    def graph_data(self) -> dict | None:
        """Raw graph data (nodes, connections) - stored in C template."""
        data = self._template.graph_data
        return data if data is not None else None

    @graph_data.setter
    def graph_data(self, value: dict | None) -> None:
        """Set graph data and bump version."""
        if value is not None:
            self._template.set_graph_data(value)
        self._version += 1

    # --- Target viewports ---

    @property
    def target_viewports(self) -> list[str]:
        """List of viewport names this pipeline targets (from ViewportFrames)."""
        return self._template.target_viewports

    # --- Compilation ---

    def compile(self) -> "RenderPipeline | None":
        """
        Compile graph data into RenderPipeline.

        Returns:
            Compiled RenderPipeline or None on error.
        """
        if not self._template.is_loaded:
            log.error(f"[ScenePipelineAsset] No graph data to compile for '{self._name}'")
            return None

        data = self._template.graph_data
        if data is None:
            log.error(f"[ScenePipelineAsset] No graph data to compile for '{self._name}'")
            return None

        # Detect format: graph has "nodes", pipeline format has "passes"
        is_graph_format = "nodes" in data and "passes" not in data

        if is_graph_format:
            return self._compile_graph()
        else:
            # Pipeline format - deserialize directly
            return self._deserialize_pipeline(data)

    def _compile_graph(self) -> "RenderPipeline | None":
        """Compile graph format data into RenderPipeline using C++ compiler."""
        try:
            pipeline = self._template.compile()
            if pipeline is not None:
                pipeline.name = self._name
            return pipeline
        except Exception as e:
            log.error(f"[ScenePipelineAsset] Failed to compile graph: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _deserialize_pipeline(self, data: dict) -> "RenderPipeline | None":
        """Deserialize pipeline format directly."""
        try:
            from termin.visualization.render.framegraph.pipeline import RenderPipeline
            from termin.visualization.core.resources import ResourceManager

            rm = ResourceManager.instance()
            pipeline = RenderPipeline.deserialize(data, rm)
            pipeline.name = self._name
            return pipeline
        except Exception as e:
            log.error(f"[ScenePipelineAsset] Failed to deserialize pipeline: {e}")
            return None

    # --- Loading ---

    def load_from_content(self, content: str, spec_data: dict | None = None) -> None:
        """Load from JSON content string."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            log.error(f"[ScenePipelineAsset] Failed to parse JSON: {e}")
            return

        # Extract UUID from data if present
        if "uuid" in data:
            self._uuid = data["uuid"]
            # Re-declare with correct UUID if needed
            existing = TcScenePipelineTemplate.find_by_uuid(self._uuid)
            if existing.is_valid:
                self._template = existing
            else:
                self._template = TcScenePipelineTemplate.declare(self._uuid, self._name)

        # Set graph data
        self._template.set_graph_data(data)
        self._template.name = self._name
        self._loaded = True
        self.mark_just_saved()

    # --- Saving ---

    def save_to_file(self, path: Path | str | None = None) -> bool:
        """
        Save graph data to .scene_pipeline file.

        Args:
            path: Target path. If None, uses source_path.

        Returns:
            True on success, False on failure.
        """
        target = Path(path) if path else self._source_path
        if target is None:
            log.error("[ScenePipelineAsset] No path specified for save")
            return False

        data = self._template.graph_data
        if data is None:
            log.error("[ScenePipelineAsset] No graph data to save")
            return False

        try:
            # Clone data to avoid modifying original
            save_data = dict(data)

            # Add UUID
            save_data["uuid"] = self.uuid

            # Write to file
            with open(target, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)

            # Update source path and mark save time
            self._source_path = target
            self.mark_just_saved()

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
            ScenePipelineAsset (may have graph_data=None on error).
        """
        path = Path(path)
        name = path.stem

        asset = cls(graph_data=None, name=name, source_path=path)

        # Read and parse immediately
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            asset.load_from_content(content)
        except Exception as e:
            log.error(f"[ScenePipelineAsset] Failed to load {path}: {e}")

        return asset

    @classmethod
    def from_graph_data(
        cls,
        graph_data: dict,
        name: str = "pipeline",
        source_path: Path | str | None = None,
    ) -> "ScenePipelineAsset":
        """
        Create ScenePipelineAsset from graph data dict.

        Args:
            graph_data: Graph data (nodes, connections).
            name: Asset name.
            source_path: Optional source path.

        Returns:
            ScenePipelineAsset.
        """
        asset = cls(graph_data=graph_data, name=name, source_path=source_path)
        asset._loaded = True
        return asset

    # --- Backwards compatibility ---

    @property
    def pipeline(self) -> "RenderPipeline | None":
        """
        DEPRECATED: Use compile() instead.
        Returns compiled pipeline for backwards compatibility.
        """
        return self.compile()
