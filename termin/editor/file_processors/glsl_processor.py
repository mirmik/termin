"""GLSL file pre-loader for .glsl files."""

from __future__ import annotations

from typing import Set

from termin.editor.project_file_watcher import FilePreLoader, PreLoadResult


class GlslPreLoader(FilePreLoader):
    """Pre-loads .glsl files - GLSL include files for shaders."""

    @property
    def priority(self) -> int:
        # Load before shaders since shaders may #include them
        return -10

    @property
    def extensions(self) -> Set[str]:
        return {".glsl"}

    @property
    def resource_type(self) -> str:
        return "glsl"

    def preload(self, path: str) -> PreLoadResult | None:
        """
        Pre-load GLSL file: read UUID from spec (lazy loading).
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


# Backward compatibility alias
GlslFileProcessor = GlslPreLoader
