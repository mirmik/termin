"""Scene pipeline file pre-loader for .scene_pipeline files."""

from __future__ import annotations

import json
from typing import Set

from termin.editor.project_file_watcher import FilePreLoader, PreLoadResult


class ScenePipelinePreLoader(FilePreLoader):
    """Pre-loads .scene_pipeline files - render pipeline configurations."""

    @property
    def priority(self) -> int:
        # Load after frame passes but before materials
        return 5

    @property
    def extensions(self) -> Set[str]:
        return {".scene_pipeline"}

    @property
    def resource_type(self) -> str:
        return "scene_pipeline"

    def preload(self, path: str) -> PreLoadResult | None:
        """
        Pre-load scene pipeline file.

        UUID is stored inside the JSON file, so we read content eagerly.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception:
            return None

        # Extract UUID from JSON content
        uuid = None
        try:
            data = json.loads(content)
            uuid = data.get("uuid")
        except json.JSONDecodeError:
            pass

        # Also check .meta file for UUID (fallback)
        spec_data = None
        if uuid is None:
            spec_data = self.read_spec_file(path)
            uuid = spec_data.get("uuid") if spec_data else None

        return PreLoadResult(
            resource_type=self.resource_type,
            path=path,
            content=content,
            uuid=uuid,
            spec_data=spec_data,
        )
