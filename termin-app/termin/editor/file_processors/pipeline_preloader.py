"""Pipeline file pre-loader for .pipeline files."""

from __future__ import annotations

from typing import Set

from termin.editor.project_file_watcher import FilePreLoader, PreLoadResult


class PipelinePreLoader(FilePreLoader):
    """Pre-loads .pipeline files - render pipeline configurations."""

    @property
    def priority(self) -> int:
        # Load after frame passes but before materials
        return 5

    @property
    def extensions(self) -> Set[str]:
        return {".pipeline"}

    @property
    def resource_type(self) -> str:
        return "pipeline"

    def preload(self, path: str) -> PreLoadResult | None:
        """
        Pre-load pipeline file: read UUID from spec (lazy loading).
        """
        # Read UUID from .meta file
        spec_data = self.read_spec_file(path)
        uuid = spec_data.get("uuid") if spec_data else None

        return PreLoadResult(
            resource_type=self.resource_type,
            path=path,
            content=None,  # Lazy loading - don't read content
            uuid=uuid,
            spec_data=spec_data,
        )
