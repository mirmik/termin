"""Pipeline file processor for .pipeline files."""

from __future__ import annotations

import json
import os
from typing import Set

from termin._native import log
from termin.editor.project_file_watcher import FileTypeProcessor


class PipelineFileProcessor(FileTypeProcessor):
    """Handles .pipeline files."""

    @property
    def extensions(self) -> Set[str]:
        return {".pipeline"}

    @property
    def resource_type(self) -> str:
        return "pipeline"

    def on_file_added(self, path: str) -> None:
        """Load new pipeline file."""
        name = os.path.splitext(os.path.basename(path))[0]

        try:
            from termin.visualization.render.framegraph.pipeline import RenderPipeline

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            pipeline = RenderPipeline.deserialize(data, self._resource_manager)

            # Store in resource manager (add pipelines dict if needed)
            if not hasattr(self._resource_manager, "pipelines"):
                self._resource_manager.pipelines = {}
            self._resource_manager.pipelines[name] = pipeline

            # Track file -> resource mapping
            if path not in self._file_to_resources:
                self._file_to_resources[path] = set()
            self._file_to_resources[path].add(name)

            self._notify_reloaded(name)

        except Exception:
            log.error(f"[PipelineProcessor] Failed to load {path}", exc_info=True)

    def on_file_changed(self, path: str) -> None:
        """Reload modified pipeline."""
        name = os.path.splitext(os.path.basename(path))[0]

        if not hasattr(self._resource_manager, "pipelines"):
            return

        if name not in self._resource_manager.pipelines:
            # File was renamed or new, treat as add
            self.on_file_added(path)
            return

        try:
            from termin.visualization.render.framegraph.pipeline import RenderPipeline

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            pipeline = RenderPipeline.deserialize(data, self._resource_manager)
            self._resource_manager.pipelines[name] = pipeline

            self._notify_reloaded(name)

        except Exception:
            log.error(f"[PipelineProcessor] Failed to reload {name}", exc_info=True)

    def on_file_removed(self, path: str) -> None:
        """Handle pipeline file deletion."""
        if path in self._file_to_resources:
            names = self._file_to_resources.pop(path)
            if hasattr(self._resource_manager, "pipelines"):
                for name in names:
                    self._resource_manager.pipelines.pop(name, None)
