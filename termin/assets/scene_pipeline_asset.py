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
        """Parse JSON content into RenderPipeline."""
        from termin.visualization.render.framegraph.pipeline import RenderPipeline
        from termin.visualization.core.resources import ResourceManager

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            log.error(f"[ScenePipelineAsset] Failed to parse JSON: {e}")
            return None

        # Extract UUID from file if present
        file_uuid = data.get("uuid")
        if file_uuid:
            self._uuid = file_uuid
            self._runtime_id = hash(self._uuid) & 0xFFFFFFFFFFFFFFFF
            self._has_uuid_in_spec = True

        # Deserialize pipeline
        try:
            rm = ResourceManager.instance()
            pipeline = RenderPipeline.deserialize(data, rm)
            pipeline.name = self._name
            return pipeline
        except Exception as e:
            log.error(f"[ScenePipelineAsset] Failed to deserialize pipeline: {e}")
            return None

    def _on_loaded(self) -> None:
        """After loading, save file if it didn't have UUID."""
        if self._source_path is not None:
            try:
                with open(self._source_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "uuid" not in data:
                    self.save_to_file()
            except Exception:
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
