"""ScenePipelineAsset - Asset for render pipeline configuration.

Stores pipeline graph source (nodes, connections).
Compilation to RenderPipeline happens on demand via compile().
File extension: .scene_pipeline

UUID is stored inside the .scene_pipeline JSON file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from termin.assets.data_asset import DataAsset
from termin._native import log

if TYPE_CHECKING:
    from termin.visualization.render.framegraph.pipeline import RenderPipeline


class ScenePipelineAsset(DataAsset[dict]):
    """
    Asset for render pipeline configuration.

    IMPORTANT: Create through ResourceManager, not directly.
    This ensures proper registration and avoids duplicates.

    Stores pipeline graph source (nodes, connections).
    Call compile() to get RenderPipeline.
    """

    _uses_binary = False  # JSON text format

    def __init__(
        self,
        graph_data: dict | None = None,
        name: str = "pipeline",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ):
        super().__init__(data=graph_data, name=name, source_path=source_path, uuid=uuid)
        self._target_viewports: list[str] = []

    # --- Graph data property ---

    @property
    def graph_data(self) -> dict | None:
        """Raw graph data (nodes, connections) - lazy-loaded from file."""
        return self.data

    @graph_data.setter
    def graph_data(self, value: dict | None) -> None:
        """Set graph data and bump version."""
        self.data = value

    # --- Content parsing ---

    def _parse_content(self, content: str) -> dict | None:
        """Parse JSON content, store as graph data (don't compile yet)."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            log.error(f"[ScenePipelineAsset] Failed to parse JSON: {e}")
            return None

        # Extract target viewports from graph if present
        self._extract_target_viewports(data)

        return data

    def _extract_target_viewports(self, data: dict) -> None:
        """Extract target viewport names from graph data."""
        self._target_viewports = []

        # Check viewport_frames list (contains frame dicts with viewport_name)
        if "viewport_frames" in data:
            for frame in data.get("viewport_frames", []):
                if isinstance(frame, dict):
                    viewport_name = frame.get("viewport_name", "")
                    if viewport_name:
                        self._target_viewports.append(viewport_name)
                elif isinstance(frame, str):
                    self._target_viewports.append(frame)

        # Also check nodes for ViewportFrame type
        if "nodes" in data:
            for node_data in data.get("nodes", []):
                if node_data.get("type") == "ViewportFrame":
                    params = node_data.get("params", {})
                    viewport_name = params.get("viewport_name", "")
                    if viewport_name and viewport_name not in self._target_viewports:
                        self._target_viewports.append(viewport_name)

    @property
    def target_viewports(self) -> list[str]:
        """List of viewport names this pipeline targets (from ViewportFrames)."""
        return self._target_viewports

    # --- Compilation ---

    def compile(self) -> "RenderPipeline | None":
        """
        Compile graph data into RenderPipeline.

        Returns:
            Compiled RenderPipeline or None on error.
        """
        if self._data is None:
            log.error(f"[ScenePipelineAsset] No graph data to compile for '{self._name}'")
            return None

        data = self._data

        # Detect format: graph has "nodes", pipeline format has "passes"
        is_graph_format = "nodes" in data and "passes" not in data

        if is_graph_format:
            return self._compile_graph(data)
        else:
            # Pipeline format - deserialize directly
            return self._deserialize_pipeline(data)

    def _compile_graph(self, data: dict) -> "RenderPipeline | None":
        """Compile graph format data into RenderPipeline using C++ compiler."""
        try:
            from termin._native.render import compile_graph_from_json

            # Convert to JSON and compile via C++
            json_str = json.dumps(data)
            pipeline = compile_graph_from_json(json_str)
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

    def _on_loaded(self) -> None:
        """After loading, save UUID to .meta file if needed."""
        pass

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

        if self._data is None:
            log.error("[ScenePipelineAsset] No graph data to save")
            return False

        try:
            # Clone data to avoid modifying original
            data = dict(self._data)

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
        asset._extract_target_viewports(graph_data)
        asset._is_loaded = True
        return asset

    # --- Backwards compatibility ---

    @property
    def pipeline(self) -> "RenderPipeline | None":
        """
        DEPRECATED: Use compile() instead.
        Returns compiled pipeline for backwards compatibility.
        """
        return self.compile()
