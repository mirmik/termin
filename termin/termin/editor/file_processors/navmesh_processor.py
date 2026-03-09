"""NavMesh file pre-loader for .navmesh files."""

from __future__ import annotations

from typing import Set

from termin.editor.project_file_watcher import FilePreLoader, PreLoadResult


class NavMeshPreLoader(FilePreLoader):
    """Pre-loads navmesh files - reads content and UUID from spec."""

    @property
    def priority(self) -> int:
        return 10  # NavMesh has no dependencies

    @property
    def extensions(self) -> Set[str]:
        return {".navmesh"}

    @property
    def resource_type(self) -> str:
        return "navmesh"

    def preload(self, path: str) -> PreLoadResult | None:
        """
        Pre-load navmesh file: only read UUID from spec (lazy loading).
        """
        # Read spec file (may contain uuid)
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
NavMeshProcessor = NavMeshPreLoader
