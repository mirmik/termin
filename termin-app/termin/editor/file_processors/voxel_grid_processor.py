"""Voxel grid file pre-loader for .voxels files."""

from __future__ import annotations

from typing import Set

from termin.editor.project_file_watcher import FilePreLoader, PreLoadResult


class VoxelGridPreLoader(FilePreLoader):
    """Pre-loads voxel grid files - reads content and UUID from spec."""

    @property
    def priority(self) -> int:
        return 10  # Voxel grids have no dependencies

    @property
    def extensions(self) -> Set[str]:
        return {".voxels"}

    @property
    def resource_type(self) -> str:
        return "voxel_grid"

    def preload(self, path: str) -> PreLoadResult | None:
        """
        Pre-load voxel grid file: only read UUID from spec (lazy loading).
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
VoxelGridProcessor = VoxelGridPreLoader
